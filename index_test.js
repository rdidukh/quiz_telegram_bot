const index = require('./static/index.js')
const assert = require('assert');
const fs = require('fs')
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
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
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

    it('#startQuestionButtons', async () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
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
                question: q
            })
        }
    });

    it('#showAnswersButtons', async () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document
        const numberOfQuestions = 3

        const controller = new index.QuizController(document)
        controller.numberOfQuestions = numberOfQuestions
        controller.init()

        const table = document.getElementById('results_table')
        assert.equal(table.rows.length, 3)
        assert.equal(table.rows[1].cells.length, numberOfQuestions + 2)

        for (var q = 1; q <= numberOfQuestions; q++) {
            const showButton = table.rows[2].cells[q + 1].firstChild
            assert.equal(showButton.tagName, 'BUTTON')
            assert.equal(showButton.textContent, 'A')
            await showButton.onclick()
            assert.equal(controller.currentQuestion, q)
            assert.equal(document.querySelector('#answers_header span').textContent, q)
        }
    });
});

describe('UpdateResultsTableTest', () => {
    it('#updatesTeamNamesAndAddsNewRows', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
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

    it('#showsPoints', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document
        const numberOfQuestions = 4

        const table = document.getElementById('results_table')
        const row = table.insertRow(-1)
        row.id = 'results_team_5002_row'
        for (var i = 1; i <= numberOfQuestions + 2; i++) {
            row.insertCell(-1).textContent = 'REMOVE'
        }

        const controller = new index.QuizController(document)
        controller.numberOfQuestions = numberOfQuestions
        controller.teamsIndex = new Map([
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
        ])
        controller.answersIndex = new Map([
            [1, new Map([
                [5001, { answer: 'Apple', points: 6 }],
                [5002, { answer: 'Banana', points: 3 }]
            ])],
            [3, new Map([
                [5001, { answer: 'Ant', points: 9 }],
                [5002, { answer: 'Bee' }]
            ])],
            [4, new Map([
                [5002, { answer: 'Bread', points: 4 }],
            ])],
        ])

        controller.updateResultsTable()

        const austriaRow = table.querySelector('#results_team_5001_row')
        assert.strictEqual(austriaRow.cells[1].textContent, '15')
        assert.strictEqual(austriaRow.cells[2].textContent, '6')
        assert.strictEqual(austriaRow.cells[3].textContent, '')
        assert.strictEqual(austriaRow.cells[4].textContent, '9')
        assert.strictEqual(austriaRow.cells[5].textContent, '')

        const belgiumRow = table.querySelector('#results_team_5002_row')
        assert.strictEqual(belgiumRow.cells[1].textContent, '7')
        assert.strictEqual(belgiumRow.cells[2].textContent, '3')
        assert.strictEqual(belgiumRow.cells[3].textContent, '')
        assert.strictEqual(belgiumRow.cells[4].textContent, '')
        assert.strictEqual(belgiumRow.cells[5].textContent, '4')
    });
});

describe('ShowAnswersForQuestionTest', () => {
    it('#overwritesValues', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        const table = document.getElementById('answers_table')
        // Create 4 initial rows with existing teams.
        for (var r = 1; r <= 4; r++) {
            table.insertRow(-1).id = 'answers_team_500' + r + '_row'
            for (var c = 0; c < 4; c++) {
                table.rows[r].insertCell(-1)
            }
            table.rows[r].cells[0] = 'REMOVE'
            table.rows[r].cells[1] = 'REMOVE'
        }

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

        assert.equal(table.rows.length, 5)
        for (var r = 1; r <= 4; r++) {
            assert.equal(table.rows[r].cells.length, 4)
        }
        assert.equal(table.rows[1].cells[0].textContent, 'Austria')
        assert.equal(table.rows[1].cells[1].textContent, 'Apple')
        assert.equal(table.rows[2].cells[0].textContent, 'Belgium')
        assert.equal(table.rows[2].cells[1].textContent, '')
        assert.equal(table.rows[3].cells[0].textContent, 'Croatia')
        assert.equal(table.rows[3].cells[1].textContent, 'Carrot')
        assert.equal(table.rows[4].cells[0].textContent, 'Denmark')
        assert.equal(table.rows[4].cells[1].textContent, '')
    });

    it('#emptyAnswersIndex', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        const table = document.getElementById('answers_table')
        table.insertRow(-1).id = 'answers_team_5001_row'
        table.insertRow(-1).id = 'answers_team_5002_row'
        for (var i = 0; i < 4; i++) {
            table.rows[1].insertCell(-1)
            table.rows[2].insertCell(-1)
        }
        table.rows[1].cells[0].textContent = 'REMOVE'
        table.rows[1].cells[1].textContent = 'REMOVE'
        table.rows[2].cells[0].textContent = 'REMOVE'
        table.rows[2].cells[1].textContent = 'REMOVE'

        const controller = new index.QuizController(document)

        controller.teamsIndex = new Map([
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
        ])
        controller.answersIndex = new Map()

        controller.showAnswersForQuestion(2)

        assert.equal(table.rows.length, 3)
        assert.equal(table.rows[1].cells.length, 4)
        assert.equal(table.rows[2].cells.length, 4)

        assert.equal(table.rows[1].cells[0].textContent, 'Austria')
        assert.equal(table.rows[1].cells[1].textContent, '')
        assert.equal(table.rows[2].cells[0].textContent, 'Belgium')
        assert.equal(table.rows[2].cells[1].textContent, '')
    });

    it('#addsNewRows', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
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
        assert.equal(table.rows.length, 3)
        assert.equal(table.rows[1].cells.length, 4)
        assert.equal(table.rows[2].cells.length, 4)

        const austriaRow = table.querySelector('#answers_team_5001_row')
        assert.equal(austriaRow.cells[0].textContent, 'Austria')
        assert.equal(austriaRow.cells[1].textContent, 'Apple')

        const belgiumRow = table.querySelector('#answers_team_5002_row')
        assert.equal(belgiumRow.cells[0].textContent, 'Belgium')
        assert.equal(belgiumRow.cells[1].textContent, 'Banana')
    });

    it('#answerCellClass', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        const controller = new index.QuizController(document)

        controller.teamsIndex = new Map([
            [5001, { name: 'Austria' }],
            [5002, { name: 'Belgium' }],
            [5003, { name: 'Croatia' }],
            [5004, { name: 'Denmark' }],
        ])
        controller.answersIndex = new Map([
            [4, new Map([
                [5001, { answer: 'Apple', points: 1 }],
                [5002, { answer: 'Banana', points: 0 }],
                [5003, { answer: 'Carrot' }],
            ])],
        ])

        controller.showAnswersForQuestion(4)

        {
            const table = document.getElementById('answers_table')
            const austriaRow = table.querySelector('#answers_team_5001_row')
            assert.deepEqual(Array.from(austriaRow.cells[1].classList.values()), ['correct_answer'])
            const belgiumRow = table.querySelector('#answers_team_5002_row')
            assert.deepEqual(Array.from(belgiumRow.cells[1].classList.values()), ['wrong_answer'])
            const croatiaRow = table.querySelector('#answers_team_5003_row')
            assert.deepEqual(Array.from(croatiaRow.cells[1].classList.values()), ['missing_answer'])
            const denmarkRow = table.querySelector('#answers_team_5004_row')
            assert.deepEqual(Array.from(denmarkRow.cells[1].classList.values()), ['missing_answer'])
        }

        controller.answersIndex = new Map([
            [4, new Map([
                [5002, { answer: 'Banana', }],
                [5003, { answer: 'Carrot', points: 0 }],
                [5004, { answer: 'Dragon Fruit', points: 1 }],
            ])],
        ])

        controller.showAnswersForQuestion(4)

        {
            const table = document.getElementById('answers_table')
            const austriaRow = table.querySelector('#answers_team_5001_row')
            assert.deepEqual(Array.from(austriaRow.cells[1].classList.values()), ['missing_answer'])
            const belgiumRow = table.querySelector('#answers_team_5002_row')
            assert.deepEqual(Array.from(belgiumRow.cells[1].classList.values()), ['missing_answer'])
            const croatiaRow = table.querySelector('#answers_team_5003_row')
            assert.deepEqual(Array.from(croatiaRow.cells[1].classList.values()), ['wrong_answer'])
            const denmarkRow = table.querySelector('#answers_team_5004_row')
            assert.deepEqual(Array.from(denmarkRow.cells[1].classList.values()), ['correct_answer'])
        }
    });

    it('#correctAnswerButtons', async () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        const fetcher = new MockFetcher()
        const controller = new index.QuizController(document, new index.Api(fetcher.get()))

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

        for (var question = 4; question <= 5; question++) {
            controller.showAnswersForQuestion(question)
            for (var teamId = 5001; teamId <= 5002; teamId++) {
                var button = document.querySelector('#answers_team_' + teamId + '_row').cells[2].firstChild
                assert.equal(button.tagName, 'BUTTON')
                assert.equal(button.classList.contains('green_text'), true)
                await button.onclick()

                var args = fetcher.calls.slice(-1).pop()
                assert.equal(args.url, '/api/setAnswerPoints')
                assert.deepEqual(JSON.parse(args.options.body), {
                    question: question,
                    points: 1,
                    team_id: teamId,
                })
            }
        }
    })

    it('#wrongAnswerButtons', async () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        const fetcher = new MockFetcher()
        const controller = new index.QuizController(document, new index.Api(fetcher.get()))

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

        for (var question = 4; question <= 5; question++) {
            controller.showAnswersForQuestion(question)
            for (var teamId = 5001; teamId <= 5002; teamId++) {
                var button = document.querySelector('#answers_team_' + teamId + '_row').cells[3].firstChild
                assert.equal(button.tagName, 'BUTTON')
                assert.equal(button.classList.contains('red_text'), true)
                await button.onclick()

                var args = fetcher.calls.slice(-1).pop()
                assert.equal(args.url, '/api/setAnswerPoints')
                assert.deepEqual(JSON.parse(args.options.body), {
                    question: question,
                    points: 0,
                    team_id: teamId,
                })
            }
        }
    })
});

describe('UpdateQuizTest', () => {
    it('#updatesQuiz', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        const controller = new index.QuizController(document)

        controller.updateQuiz({
            status: {
                update_id: 123,
                quiz_id: 'test',
                language: 'lang',
                question: 4,
                registration: false,
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

        const statusTable = document.getElementById('status_table')
        assert.equal(statusTable.rows[0].cells[1].textContent, 'test')
        assert.equal(statusTable.rows[1].cells[1].textContent, 'lang')
        assert.equal(statusTable.rows[2].cells[1].textContent, '4')
        assert.equal(statusTable.rows[4].cells[1].textContent, '2020-01-02 03:04:05')
    });

    it('#registrationFalse', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        var statusTable = document.getElementById('status_table')
        var startButton = statusTable.rows[3].cells[1].firstElementChild

        startButton.classList.add('disabled')

        const controller = new index.QuizController(document)

        controller.updateQuiz({
            status: {
                update_id: 123,
                quiz_id: 'test',
                language: 'lang',
                question: 4,
                registration: false,
                time: '2020-01-02 03:04:05'
            },
            teams: [],
            answers: []
        })

        var statusTable = document.getElementById('status_table')

        var startButton = statusTable.rows[3].cells[1].firstElementChild
        var stopButton = statusTable.rows[3].cells[2].firstElementChild

        assert.equal(startButton.classList.contains('disabled'), false)
        assert.equal(stopButton.classList.contains('disabled'), true)
    });

    it('#registrationTrue', () => {
        const indexHtml = fs.readFileSync('static/index.html')
        const dom = new jsdom.JSDOM(indexHtml);
        const document = dom.window.document

        var statusTable = document.getElementById('status_table')
        var stopButton = statusTable.rows[3].cells[2].firstElementChild

        stopButton.classList.add('disabled')

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
            teams: [],
            answers: []
        })

        var statusTable = document.getElementById('status_table')

        var startButton = statusTable.rows[3].cells[1].firstElementChild
        var stopButton = statusTable.rows[3].cells[2].firstElementChild

        assert.equal(startButton.classList.contains('disabled'), true)
        assert.equal(stopButton.classList.contains('disabled'), false)
    });
});