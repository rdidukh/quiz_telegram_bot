const assert = require('assert');
const fs = require('fs')
const jsdom = require("jsdom");

const { MockApi } = require('./mock_api.js')
const { Controller } = require('./static/send_results.js')

describe('Init', () => {
    let document = null
    let api = null
    let controller = null

    beforeEach(() => {
        const indexHtml = fs.readFileSync('static/send_results.html')
        const dom = new jsdom.JSDOM(indexHtml);
        document = dom.window.document
        api = new MockApi()
        api.mockGetUpdates = async () => {
            return {
                teams: [
                    { id: 5001, name: 'Austria' },
                    { id: 5002, name: 'Belgium' },
                    { id: 5003, name: 'Croatia' }
                ]
            }
        }
        api.mockSendResults = async () => { }

        controller = new Controller(document, api)
    })


    it('#createsCheckboxes', async () => {
        await controller.init()

        assert.deepEqual(api.getUpdatesCalls, [[-1, 0, -1]])

        const form = document.getElementById('send_results_form')
        const austriaLabel = form.children.item(0)
        const belgiumLabel = form.children.item(1)
        const croatiaLabel = form.children.item(2)

        assert.equal(austriaLabel.textContent, 'Austria')
        assert.equal(belgiumLabel.textContent, 'Belgium')
        assert.equal(croatiaLabel.textContent, 'Croatia')

        const austriaCheckbox = austriaLabel.firstChild
        const belgiumCheckbox = belgiumLabel.firstChild
        const croatiaCheckbox = croatiaLabel.firstChild

        assert.equal(austriaCheckbox.tagName, 'INPUT')
        assert.equal(belgiumCheckbox.tagName, 'INPUT')
        assert.equal(croatiaCheckbox.tagName, 'INPUT')

        assert.equal(austriaCheckbox.type, 'checkbox')
        assert.equal(belgiumCheckbox.type, 'checkbox')
        assert.equal(croatiaCheckbox.type, 'checkbox')

        assert.equal(austriaCheckbox.id, 'team_5001_checkbox')
        assert.equal(belgiumCheckbox.id, 'team_5002_checkbox')
        assert.equal(croatiaCheckbox.id, 'team_5003_checkbox')

        assert.equal(austriaCheckbox.checked, true)
        assert.equal(belgiumCheckbox.checked, true)
        assert.equal(croatiaCheckbox.checked, true)
    })


    describe('SendResultsButton', async () => {
        let button

        beforeEach(() => {
            button = document.getElementById('send_results_button')
        })

        it('#noTeamsSelected', async () => {
            await controller.init()
            document.getElementById('team_5001_checkbox').checked = false
            document.getElementById('team_5002_checkbox').checked = false
            document.getElementById('team_5003_checkbox').checked = false

            await button.onclick()

            assert.deepEqual(api.sendResultsCalls, [])
        })

        it('#oneTeamSelected', async () => {
            await controller.init()
            const checkbox5001 = document.getElementById('team_5001_checkbox')
            const checkbox5002 = document.getElementById('team_5002_checkbox')
            const checkbox5003 = document.getElementById('team_5003_checkbox')

            checkbox5001.checked = false
            checkbox5002.checked = true
            checkbox5003.checked = false

            await button.onclick()

            assert.deepEqual(api.sendResultsCalls, [[5002]])

            assert.equal(checkbox5001.parentElement.style.color, '')
            assert.equal(checkbox5002.parentElement.style.color, 'green')
            assert.equal(checkbox5003.parentElement.style.color, '')
        })

        it('#manyTeamsSelected', async () => {
            await controller.init()
            const checkbox5001 = document.getElementById('team_5001_checkbox')
            const checkbox5002 = document.getElementById('team_5002_checkbox')
            const checkbox5003 = document.getElementById('team_5003_checkbox')

            checkbox5001.checked = true
            checkbox5002.checked = false
            checkbox5003.checked = true

            await button.onclick()

            assert.deepEqual(api.sendResultsCalls, [[5001], [5003]])

            assert.equal(checkbox5001.parentElement.style.color, 'green')
            assert.equal(checkbox5002.parentElement.style.color, '')
            assert.equal(checkbox5003.parentElement.style.color, 'green')
        })

        it('#oneTeamThrows', async () => {
            api.mockSendResults = async (teamId) => {
                console.log('Mock send results: ' + teamId)
                if (teamId == 5001) throw '#error!'
            }

            await controller.init()
            const checkbox5001 = document.getElementById('team_5001_checkbox')
            const checkbox5002 = document.getElementById('team_5002_checkbox')
            const checkbox5003 = document.getElementById('team_5003_checkbox')

            checkbox5001.checked = true
            checkbox5002.checked = false
            checkbox5003.checked = true

            await button.onclick()

            assert.deepEqual(api.sendResultsCalls, [[5001], [5003]])

            assert.equal(checkbox5001.parentElement.style.color, 'red')
            assert.equal(checkbox5002.parentElement.style.color, '')
            assert.equal(checkbox5003.parentElement.style.color, 'green')
        })
    })
})
