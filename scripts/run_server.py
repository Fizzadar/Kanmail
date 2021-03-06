#!/usr/bin/env python

import os
import sys

sys.path.append('.')  # noqa: E402
os.environ['KANMAIL_MODE'] = 'server'  # noqa: E402

from kanmail.server.app import app, boot
from kanmail.settings.constants import DEBUG, SERVER_PORT


# Bootstrap the server, but don't prep cheroot itself (we'll use Flask devserver)
boot(prepare_server=False)

# Run the server
app.run(
    host='0.0.0.0',
    port=SERVER_PORT,
    threaded=True,
    debug=DEBUG,
)
