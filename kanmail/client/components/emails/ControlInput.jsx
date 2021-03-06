import _ from 'lodash';
import React from 'react';
import PropTypes from 'prop-types';
import Select from 'react-select';

import keyboard from 'keyboard.js';

import controlStore from 'stores/control.js';
import folderStore from 'stores/folders.js';
import { subscribe } from 'stores/base.jsx';

import { capitalizeFirstLetter } from 'util/string.js';
import { moveOrCopyThread } from 'util/threads.js';


@subscribe(folderStore)
class ControlInput extends React.Component {
    static propTypes = {
        folders: PropTypes.array.isRequired,
        action: PropTypes.string,
        subject: PropTypes.string,
        moveData: PropTypes.object,
    }

    handleSelectChange = (value) => {
        const { action, moveData } = this.props;

        if (action !== 'move') {
            throw new Error(`${action} is not a valid control action!`);
        }

        moveOrCopyThread(
            moveData,
            value.value,
            keyboard.setMovingCurrentThread,
        );
        this.handleClose();
    }

    handleClose = () => {
        controlStore.close();
        setTimeout(keyboard.enable, 0);  // prevent the *current* keyboard event executing
    }

    render () {
        const folderOptions = _.map(this.props.folders, folderName => ({
            value: folderName,
            label: folderName,
        }));

        return (
            <div>
                <section id="control-background">
                    <section id="control">
                        <p>
                            {capitalizeFirstLetter(this.props.action)}&nbsp;
                            <strong>{this.props.subject}</strong>...
                        </p>
                        <Select
                            id="control-input"
                            classNamePrefix="react-select"
                            options={folderOptions}
                            autoFocus={true}
                            openMenuOnFocus={true}
                            closeMenuOnSelect={false}
                            menuIsOpen={true}
                            onMenuClose={this.handleClose}
                            onChange={this.handleSelectChange}
                            onFocus={keyboard.disable}
                            onBlur={keyboard.enable}
                        />
                    </section>
                </section>
            </div>
        );
    }
}


@subscribe(controlStore)
export default class ControlInputWrapper extends React.Component {
    static propTypes = {
        open: PropTypes.bool.isRequired,
        action: PropTypes.string,
        subject: PropTypes.string,
        moveData: PropTypes.object,
    }

    render() {
        if (!this.props.open) {
            return null;
        }

        return <ControlInput {...this.props} />;
    }
}
