import email.header
import quopri
import re

from base64 import b64decode

# from flanker import mime

from kanmail.log import logger


def format_address(address):
    bits = []

    if address.mailbox:
        bits.append(address.mailbox.decode())

    if address.host:
        bits.append(address.host.decode())

    return '@'.join(bits)


def make_addresses(addresses):
    if not addresses:
        return []

    return [
        (
            decode_header(address.name) if address.name else None,
            format_address(address),
        )
        for address in addresses
    ]


def make_email_headers(account, folder, uid, data, parts):
    # Parse references header into list of reference message IDs
    headers = extract_headers(
        data[b'BODY[HEADER.FIELDS (REFERENCES CONTENT-TRANSFER-ENCODING)]'],
    )

    references = headers.get('References')
    if references:
        references = references.split()

    body_meta = None

    if '1' in parts:
        body_meta = parts['1']

    if not body_meta:
        content_transfer_encoding = headers.get('Content-Transfer-Encoding')
        if content_transfer_encoding:
            body_meta = {
                'encoding': content_transfer_encoding,
            }

    encoding = body_meta.get('encoding') if body_meta else None

    # Attempt to extract an excerpt
    excerpt = extract_excerpt(
        data[b'BODY[1]<0>'],
        body_meta,
    )

    # Make the summary dict!
    envelope = data[b'ENVELOPE']
    subject = decode_header(envelope.subject)

    return {
        'uid': uid,
        'seq': data[b'SEQ'],
        'flags': data[b'FLAGS'],
        'size': data[b'RFC822.SIZE'],
        'excerpt': excerpt,
        'content_encoding': encoding,
        'parts': parts,

        # Internal meta
        'account_name': account.name,
        'server_folder_name': folder.name,

        # Envelope data
        'date': envelope.date.isoformat(),
        'subject': subject,

        # Address data
        'from': make_addresses(envelope.from_),
        'to': make_addresses(envelope.to),
        'send': make_addresses(envelope.sender),
        'cc': make_addresses(envelope.cc),
        'bcc': make_addresses(envelope.bcc),
        'reply_to': make_addresses(envelope.reply_to),

        # Threading
        'in_reply_to': envelope.in_reply_to,
        'message_id': envelope.message_id,
        'references': references,
    }


def decode_header(subject):
    if subject is None:
        return ''

    bits = []

    if isinstance(subject, bytes):
        subject = subject.decode()

    for output, encoding in email.header.decode_header(subject):
        if encoding:
            output = output.decode(encoding)

        bits.append(output)

    return ''.join(bits)


def decode_string(string, string_meta=None):
    encoding = None
    charset = None

    if string_meta:
        # Encoding *must* be provided
        encoding = string_meta['encoding'].lower()

        if 'charset' in string_meta:
            charset = string_meta['charset'].lower()

    # Remove any quoted printable stuff
    if encoding == 'quoted-printable':
        string = quopri.decodestring(string)

    # Remove any base64 stuff
    if encoding == 'base64':
        string = b64decode(string)

    if charset:
        charset = charset.decode()
        string = string.decode(charset, 'ignore')

    if isinstance(string, bytes):
        try:
            string = string.decode()
        except UnicodeDecodeError:
            pass

    return string


def _extract_excerpt(raw_body, raw_body_meta):
    # Decode the body first
    raw_body = decode_string(raw_body, raw_body_meta)

    # Remove any style tags *and* content
    raw_body = re.sub(r'<style.*>.*(?:</style>)?', '', raw_body, flags=re.DOTALL)

    # Remove any other tags
    raw_body = re.sub(r'<.*?>', '', raw_body)

    # Remove any tag starts (ie <thing ... with no end due to cutoff)
    raw_body = re.sub(r'<[^>]*', '', raw_body)

    lines = []

    for line in raw_body.splitlines():
        line = line.strip()

        if not line:
            continue

        if line[0] in ('#', '-'):
            continue

        lines.append(line)

    if not lines:
        return

    body = '\n'.join(lines)
    return body


def extract_excerpt(raw_body, raw_body_meta):
    try:
        return _extract_excerpt(
            raw_body,
            raw_body_meta,
        )

    except Exception as e:
        logger.critical('Could not extract excerpt: {0} (data={1}, meta={2})'.format(
            e, raw_body, raw_body_meta,
        ))


def extract_headers(raw_message):
    message = decode_string(raw_message)

    parser = email.parser.HeaderParser()

    headers = dict(parser.parsestr(message).items())

    return headers


def _parse_bodystructure(bodystructure, item_number=None):
    items = {}

    type_or_bodies = bodystructure[0]

    if isinstance(type_or_bodies, list):
        for i, body in enumerate(type_or_bodies, 1):
            if item_number:
                nested_item_number = '{0}.{1}'.format(item_number, i)
            else:
                nested_item_number = '{0}'.format(i)

            items.update(_parse_bodystructure(
                body,
                item_number=nested_item_number,
            ))

    else:
        subtype = bodystructure[1]
        encoding = bodystructure[5]
        size = bodystructure[6]

        item_number = item_number or 1

        data = {
            'type': type_or_bodies.decode(),
            'subtype': subtype.decode(),
            'encoding': encoding.decode(),
            'size': size,
        }

        charset_or_name = bodystructure[2]

        if charset_or_name:
            charset_or_name_key, charset_or_name = bodystructure[2][:2]
            if charset_or_name_key == b'NAME':
                data['name'] = charset_or_name
            else:
                data['charset'] = charset_or_name

        items[item_number] = data

    return items


def parse_bodystructure(bodystructure):
    try:
        items = _parse_bodystructure(bodystructure)
    except Exception as e:
        logger.critical('Could not parse bodystructure: {0} (struct={1})'.format(
            e, bodystructure,
        ))

        raise

    # Attach shortcuts -> part IDs
    items['attachments'] = []

    for number, part in list(items.items()):
        if number in ('attachments', 'html', 'plain'):
            continue

        if part['type'] == 'TEXT':
            if part['subtype'] == 'HTML':
                items['html'] = number
                continue

            if part['subtype'] == 'PLAIN':
                items['plain'] = number
                continue

        items['attachments'].append(number)

    return items