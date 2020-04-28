import { Api } from './api.js'

export class Controller {
    constructor(document, api) {
        this.document = document
        this.api = api
    }

    async init() {
        // Get teams only.
        const updates = await this.api.getUpdates(-1, 0, -1)
        const teams = updates.teams

        const form = this.document.getElementById('send_results_form')

        for (let team of teams) {
            const id = 'team_' + team.id + '_checkbox'
            const checkbox = this.document.createElement('input')
            checkbox.id = id
            checkbox.type = 'checkbox'
            checkbox.checked = true

            const label = this.document.createElement('label')
            label.appendChild(checkbox)
            label.appendChild(this.document.createTextNode(team.name))
            form.appendChild(label)
        }

        const button = this.document.getElementById('send_results_button')
        button.onclick = async () => {
            for (let team of teams) {
                const checkbox = this.document.getElementById('team_' + team.id + '_checkbox')
                if (checkbox.checked === true) {
                    try {
                        await this.api.sendResults(team.id)
                        console.log('Results sent to team ' + team.name + ' (' + team.id + ')')
                        checkbox.parentElement.style.color = 'green'
                    } catch (e) {
                        console.error('Could not send results to team ' + team.name + ' (' + team.id + '): ' + e)
                        checkbox.parentElement.style.color = 'red'
                    }
                }
            }
        }
    }
}

if (typeof (window) !== 'undefined') {
    window.onload = () => {
        const api = new Api(fetch.bind(window))
        const controller = new Controller(document, api)
        controller.init()
    }
}
