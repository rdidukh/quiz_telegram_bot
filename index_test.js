const index = require('./static/index.js')
const assert = require('assert');
const jsdom = require("jsdom");

class MockFetcher {
    constructor() {
        this.calls = []
    }

    get() {
        return async (url, options) => {
            this.calls.push({ url: url, options: options })
            return { text: () => '{}', status: 200 }
        }
    }
}

describe('InitResultsTable', () => {
    it('#propagatesQuestionNumbers', () => {
        const dom = new jsdom.JSDOM(`<html><body><table id="results_table"></table></body></html>`);
        const document = dom.window.document
        const numberOfQuestions = 3

        const controller = new index.QuizController(document, new index.Api())
        controller.numberOfQuestions = numberOfQuestions
        controller.init()

        const table = document.getElementById('results_table')
        assert.equal(table.rows.length, 3)
        assert.equal(table.rows[0].cells.length, 5)

        assert.equal(table.rows[0].cells[1].textContent, 'Total')
        assert.equal(table.rows[0].cells[2].textContent, '1')
        assert.equal(table.rows[0].cells[3].textContent, '2')
        assert.equal(table.rows[0].cells[4].textContent, '3')
    });

    it('#propagatesStartQuestionButtons', async () => {
        const dom = new jsdom.JSDOM(`<html><body><table id="results_table"></table></body></html>`);
        const document = dom.window.document
        const numberOfQuestions = 3

        const fetcher = new MockFetcher()
        const controller = new index.QuizController(document, new index.Api(fetcher.get()))
        controller.numberOfQuestions = numberOfQuestions
        controller.init()

        const table = document.getElementById('results_table')
        assert.equal(table.rows.length, numberOfQuestions)
        assert.equal(table.rows[1].cells.length, numberOfQuestions + 2)

        for (var q = 1; q <= numberOfQuestions; q++) {
            const startButton = table.rows[1].cells[q + 1].firstChild
            assert.equal(startButton.tagName, 'BUTTON')
            assert.equal(startButton.textContent, '>')
            await startButton.onclick()

            args = fetcher.calls.slice(-1).pop()
            assert.equal(args.url, '/api/startQuestion')
            assert.deepEqual(JSON.parse(args.options.body), {
                question_id: '0' + q
            })
        }
    });

    it('#propagatesShowAnswersButtons', async () => {
        const dom = new jsdom.JSDOM(`<html><body><table id="results_table"></table></body></html>`);
        const document = dom.window.document
        const numberOfQuestions = 3

        const controller = new index.QuizController(document)
        controller.numberOfQuestions = numberOfQuestions
        controller.init()

        const table = document.getElementById('results_table')
        assert.equal(table.rows.length, numberOfQuestions)
        assert.equal(table.rows[1].cells.length, numberOfQuestions + 2)

        for (var q = 1; q <= numberOfQuestions; q++) {
            const showButton = table.rows[2].cells[q + 1].firstChild
            assert.equal(showButton.tagName, 'BUTTON')
            assert.equal(showButton.textContent, 'A')
            await showButton.onclick()
            assert.equal(controller.currentQuestion, q)
        }
    });
});

describe('UpdateResultsTableTest', () => {
    it('#updatesTeamNamesAndAddsNewRows', () => {
        const dom = new jsdom.JSDOM(`<html><body><table id="results_table"></table></body></html>`);
        const document = dom.window.document
        const numberOfQuestions = 3

        const table = document.getElementById('results_table')
        const row = table.insertRow(-1)
        row.id = 'results_team_5002_row'
        for (var i = 1; i <= numberOfQuestions + 2; i++) {
            row.insertCell(-1)
        }
        row.cells[0].textContent = 'REMOVE'

        const controller = new index.QuizController(document)
        controller.numberOfQuestions = numberOfQuestions

        controller.teamsIndex = new Map([
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
        ])

        controller.updateResultsTable()

        assert.equal(table.rows.length, 2)
        assert.equal(table.rows[0].cells[0].textContent, 'Belgium')
        assert.equal(table.rows[1].id, 'results_team_5001_row')
        assert.equal(table.rows[1].cells.length, 5)
        assert.equal(table.rows[1].cells[0].textContent, 'Austria')
    });
});

describe('ShowAnswersForQuestionTest', () => {
    it('#overwritesValues', () => {
        const dom = new jsdom.JSDOM(`<html><body><table id="answers_table"></table></body></html>`);
        const document = dom.window.document

        const table = document.getElementById('answers_table')
        table.insertRow(-1).id = 'answers_team_5001_row'
        table.insertRow(-1).id = 'answers_team_5002_row'
        table.insertRow(-1).id = 'answers_team_5003_row'
        table.insertRow(-1).id = 'answers_team_5004_row'
        for (var r = 0; r < 4; r++) {
            for (var c = 0; c < 4; c++) {
                table.rows[r].insertCell(-1)
            }
        }
        table.rows[0].cells[0] = 'REMOVE'
        table.rows[0].cells[1] = 'REMOVE'
        table.rows[1].cells[0] = 'REMOVE'
        table.rows[1].cells[1] = 'REMOVE'
        table.rows[2].cells[0] = 'REMOVE'
        table.rows[2].cells[1] = 'REMOVE'
        table.rows[3].cells[0] = 'REMOVE'
        table.rows[3].cells[1] = 'REMOVE'

        const controller = new index.QuizController(document)

        controller.teamsIndex = new Map([
            // TODO: more teams.
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
            [5003, { name: 'Croatia' }],
            [5004, { name: 'Denmark' }],
        ])
        controller.answersIndex = new Map([
            [3, new Map([
                [5001, { answer: 'Apple' }],
                [5003, { answer: 'Carrot' }],
                // No answers for team Belgium & Denmark.
            ])],
        ])

        controller.showAnswersForQuestion(3)

        assert.equal(controller.currentQuestion, 3)

        assert.equal(table.rows.length, 4)
        assert.equal(table.rows[0].cells.length, 4)
        assert.equal(table.rows[1].cells.length, 4)

        assert.equal(table.rows[0].cells[0].textContent, 'Austria')
        assert.equal(table.rows[0].cells[1].textContent, 'Apple')
        assert.equal(table.rows[1].cells[0].textContent, 'Belgium')
        assert.equal(table.rows[1].cells[1].textContent, '')
        assert.equal(table.rows[2].cells[0].textContent, 'Croatia')
        assert.equal(table.rows[2].cells[1].textContent, 'Carrot')
        assert.equal(table.rows[3].cells[0].textContent, 'Denmark')
        assert.equal(table.rows[3].cells[1].textContent, '')
    });

    it('#emptyAnswersIndex', () => {
        const dom = new jsdom.JSDOM(`<html><body><table id="answers_table"></table></body></html>`);
        const document = dom.window.document

        const table = document.getElementById('answers_table')
        table.insertRow(-1).id = 'answers_team_5001_row'
        table.insertRow(-1).id = 'answers_team_5002_row'
        for (var i = 0; i < 4; i++) {
            table.rows[0].insertCell(-1)
            table.rows[1].insertCell(-1)
        }
        table.rows[0].cells[0] = 'REMOVE'
        table.rows[0].cells[1] = 'REMOVE'
        table.rows[1].cells[0] = 'REMOVE'
        table.rows[1].cells[1] = 'REMOVE'

        const controller = new index.QuizController(document)

        controller.teamsIndex = new Map([
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
        ])
        controller.answersIndex = new Map()

        controller.showAnswersForQuestion(2)

        assert.equal(table.rows.length, 2)
        assert.equal(table.rows[0].cells.length, 4)
        assert.equal(table.rows[1].cells.length, 4)

        assert.equal(table.rows[0].cells[0].textContent, 'Austria')
        assert.equal(table.rows[0].cells[1].textContent, '')
        assert.equal(table.rows[1].cells[0].textContent, 'Belgium')
        assert.equal(table.rows[1].cells[1].textContent, '')
    });

    it('#addsNewRows', () => {
        const dom = new jsdom.JSDOM('<html><body><table id="answers_table"></table></body></html>');
        const document = dom.window.document

        const controller = new index.QuizController(document)

        controller.teamsIndex = new Map([
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
        ])
        controller.answersIndex = new Map([
            [4, new Map([
                [5001, { answer: 'Apple' }],
                [5002, { answer: 'Banana' }]
            ])],
        ])
        controller.showAnswersForQuestion(4)

        const table = document.getElementById('answers_table')
        assert.equal(table.rows.length, 2)
        assert.equal(table.rows[0].cells.length, 4)
        assert.equal(table.rows[1].cells.length, 4)

        const austriaRow = table.querySelector('#answers_team_5001_row')
        assert.equal(austriaRow.cells[0].textContent, 'Austria')
        assert.equal(austriaRow.cells[1].textContent, 'Apple')

        const belgiumRow = table.querySelector('#answers_team_5002_row')
        assert.equal(belgiumRow.cells[0].textContent, 'Belgium')
        assert.equal(belgiumRow.cells[1].textContent, 'Banana')
    });
});

describe('UpdateQuizTest', () => {
    it('#updatesQuiz', () => {
        const dom = new jsdom.JSDOM(`
            <html>
                <body>
                    <table id="status_table">
                    <table id="results_table"></table>
                    <table id="answers_table"></table>
                </body>
            </html>`);
        const document = dom.window.document

        const statusTable = document.getElementById('status_table')
        for (var i = 1; i <= 5; i++) {
            const row = statusTable.insertRow(-1)
            row.insertCell(-1)
            row.insertCell(-1)
        }

        const controller = new index.QuizController(document)

        controller.updateQuiz({
            status: {
                update_id: 123,
                quiz_id: 'test',
                language: 'lang',
                question: 4,
                registration: true,
                time: '2020-01-02 03:04:05'
            },
            teams: [
                { update_id: 456, id: 5001, name: 'Liverpool' },
                { update_id: 455, id: 5002, name: 'Tottenham' },
            ],
            answers: [
                { update_id: 788, team_id: 5003, question: 2, answer: 'Carrot' },
                { update_id: 789, team_id: 5001, question: 4, answer: 'Apple' },
            ]
        })

        assert.equal(controller.lastSeenStatusUpdateId, 123)
        assert.equal(controller.lastSeenTeamsUpdateId, 456)
        assert.equal(controller.lastSeenAnswersUpdateId, 789)

        assert.equal(controller.teamsIndex.size, 2)
        assert.deepEqual(controller.teamsIndex.get(5001),
            { update_id: 456, id: 5001, name: 'Liverpool' })
        assert.deepEqual(controller.teamsIndex.get(5002),
            { update_id: 455, id: 5002, name: 'Tottenham' })

        assert.equal(controller.answersIndex.size, 2)
        assert.deepEqual(controller.answersIndex.get(2).get(5003),
            { update_id: 788, team_id: 5003, question: 2, answer: 'Carrot' })
        assert.deepEqual(controller.answersIndex.get(4).get(5001),
            { update_id: 789, team_id: 5001, question: 4, answer: 'Apple' })

        assert.equal(controller.currentQuestion, 1)

        assert.equal(statusTable.rows[0].cells[1].textContent, 'test')
        assert.equal(statusTable.rows[1].cells[1].textContent, 'lang')
        assert.equal(statusTable.rows[2].cells[1].textContent, '4')
        assert.equal(statusTable.rows[3].cells[1].textContent, 'true')
        assert.equal(statusTable.rows[4].cells[1].textContent, '2020-01-02 03:04:05')
    });
});