import { Api } from './api.js'

const correctAnswerButtonText = '\u2714' // ✔
const wrongAnswerButtonText = '\u2716' // ✖

function updateTextContent(element, newTextContent) {
    if (element.textContent !== newTextContent) {
        element.textContent = newTextContent
    }
}

export class QuizController {
    constructor(document, api) {
        this.document = document
        this.api = api
        this.numberOfQuestions = 24
        // teamId -> Team.
        this.teamsIndex = new Map()
        // question -> teamId -> Answer
        this.answersIndex = new Map()
        this.runningQuestion = null
        this.currentQuestion = 1
        this.lastSeenStatusUpdateId = 0
        this.lastSeenTeamsUpdateId = 0
        this.lastSeenAnswersUpdateId = 0
    }

    init() {
        this.initResultsTable()

        this.document.getElementById('start_registration_button').onclick = async () => {
            this.api.startRegistration()
        }

        this.document.getElementById('stop_registration_button').onclick = async () => {
            this.api.stopRegistration()
        }

        this.document.getElementById('start_question_button').onclick = async () => {
            this.api.startQuestion(this.currentQuestion)
        }

        this.document.getElementById('stop_question_button').onclick = async () => {
            this.api.stopQuestion()
        }

        this.document.getElementById('previous_question_button').onclick = async () => {
            var question = this.currentQuestion - 1
            if (question <= 0) {
                question = this.numberOfQuestions
            }
            this.showAnswersForQuestion(question)
        }

        this.document.getElementById('next_question_button').onclick = async () => {
            var question = this.currentQuestion + 1
            if (question > this.numberOfQuestions) {
                question = 1
            }
            this.showAnswersForQuestion(question)
        }

        this.hightlightResultsTable()
    }

    updateStatusTable(status) {
        const table = this.document.getElementById('status_table')
        updateTextContent(table.rows[0].cells[1], status.quiz_id)
        updateTextContent(table.rows[1].cells[1], status.language)
        updateTextContent(table.rows[2].cells[1], status.question)
        updateTextContent(table.rows[4].cells[1], status.time)

        const regStartButton = table.rows[3].cells[1].firstElementChild
        const regStopButton = table.rows[3].cells[2].firstElementChild

        if (status.question != null) {
            regStartButton.classList.add('disabled')
            regStopButton.classList.add('disabled')
        } else if (status.registration === true) {
            regStartButton.classList.add('disabled')
            regStopButton.classList.remove('disabled')
        } else {
            regStartButton.classList.remove('disabled')
            regStopButton.classList.add('disabled')
        }
    }

    initResultsTable() {
        const table = this.document.getElementById('results_table')
        const resultsTableHeaderRow = table.insertRow()
        resultsTableHeaderRow.insertCell().textContent = 'Team'
        resultsTableHeaderRow.insertCell().textContent = 'Total'

        for (let question = 1; question <= this.numberOfQuestions; question++) {
            const cell = resultsTableHeaderRow.insertCell()
            cell.textContent = question
            cell.onclick = () => {
                this.showAnswersForQuestion(question)
            }
        }
    }

    hightlightResultsTable() {
        const table = this.document.getElementById('results_table')

        for (let r = 0; r < table.rows.length; r++) {
            for (let c = 2; c < table.rows[r].cells.length; c++) {
                if (this.currentQuestion + 1 === c) {
                    table.rows[r].cells[c].classList.add('current_question')
                } else {
                    table.rows[r].cells[c].classList.remove('current_question')
                }

                if (this.runningQuestion + 1 === c) {
                    table.rows[r].cells[c].classList.add('running_question')
                } else {
                    table.rows[r].cells[c].classList.remove('running_question')
                }
            }
        }
    }

    updateResultsTable() {
        const table = this.document.getElementById('results_table')

        for (const [teamId, team] of this.teamsIndex) {
            const rowId = 'results_team_' + teamId + '_row'
            var row = this.document.getElementById(rowId)
            if (!row) {
                row = table.insertRow()
                row.id = rowId

                for (let q = 1; q <= this.numberOfQuestions + 2; q++) {
                    row.insertCell()
                }
            }

            var totalPoints = 0

            for (let question = 1; question <= this.numberOfQuestions; question++) {
                if (this.answersIndex.has(question)) {
                    var answers = this.answersIndex.get(question)
                    if (answers.has(teamId)) {
                        var points = answers.get(teamId).points
                    } else {
                        var points = null
                    }
                } else {
                    var points = null
                }

                if (points != null) {
                    totalPoints += points
                }

                updateTextContent(row.cells[question + 1], points)
            }

            updateTextContent(row.cells[0], team.name)
            updateTextContent(row.cells[1], totalPoints)
        }

        this.hightlightResultsTable()
    }

    highlightQuestionHeader() {
        const header = this.document.getElementById('question_header')
        if (this.currentQuestion === this.runningQuestion) {
            header.classList.add('running_question')
        } else {
            header.classList.remove('running_question')
        }
    }

    showAnswersForQuestion(question) {
        this.currentQuestion = question
        this.document.getElementById('question_span').textContent = question

        this.updateAnswersTable()
        this.hightlightResultsTable()
        this.highlightQuestionHeader()
    }

    updateStartStopQuestionButtons(status) {
        const startButton = this.document.getElementById('start_question_button')
        const stopButton = this.document.getElementById('stop_question_button')
        if (status.registration === true) {
            startButton.classList.add('disabled')
            stopButton.classList.add('disabled')
        } else if (status.question != null) {
            startButton.classList.add('disabled')
            stopButton.classList.remove('disabled')
        } else {
            startButton.classList.remove('disabled')
            stopButton.classList.add('disabled')
        }
    }

    updateAnswersTable() {
        const table = this.document.getElementById('answers_table')

        if (this.answersIndex.has(this.currentQuestion)) {
            var answers = this.answersIndex.get(this.currentQuestion)
        } else {
            var answers = new Map()
        }

        for (const [teamId, team] of this.teamsIndex) {
            const rowId = 'answers_team_' + teamId + '_row'
            var row = this.document.getElementById(rowId)
            if (!row) {
                row = table.insertRow()
                row.id = rowId

                const correctButton = this.document.createElement('button')
                correctButton.textContent = correctAnswerButtonText
                correctButton.classList.add('green_text')
                correctButton.onclick = async () => {
                    this.api.setAnswerPoints(this.currentQuestion, teamId, 1)
                }

                const wrongButton = this.document.createElement('button')
                wrongButton.textContent = wrongAnswerButtonText
                wrongButton.classList.add('red_text')
                wrongButton.onclick = async () => {
                    this.api.setAnswerPoints(this.currentQuestion, teamId, 0)
                }

                row.insertCell().textContent = team.name
                row.insertCell() // Answer.
                row.insertCell().appendChild(correctButton)
                row.insertCell().appendChild(wrongButton)
            }

            if (answers.has(teamId)) {
                var answer = answers.get(teamId)
            } else {
                // No answer to the question for this team.
                var answer = { text: '', points: null }
            }

            if (answer.points == null) {
                var cellClass = 'missing_answer'
            } else if (answer.points > 0) {
                var cellClass = 'correct_answer'
            } else if (answer.points <= 0) {
                var cellClass = 'wrong_answer'
            }

            updateTextContent(row.cells[0], team.name)
            updateTextContent(row.cells[1], answer.answer)
            row.cells[1].classList.remove('correct_answer', 'wrong_answer', 'missing_answer')
            row.cells[1].classList.add(cellClass)
        }
    }

    updateQuiz(updates) {
        if (updates.status) {
            this.lastSeenStatusUpdateId = updates.status.update_id
            this.runningQuestion = updates.status.question
            console.log('Status update. update_id: ' + updates.status.update_id)
            this.updateStatusTable(updates.status)
            this.updateStartStopQuestionButtons(updates.status)
        }

        // Update teams index.
        for (const team of updates.teams) {
            this.lastSeenTeamsUpdateId = Math.max(this.lastSeenTeamsUpdateId, team.update_id)
            this.teamsIndex.set(team.id, team)
            console.log('Team update. Name: "' + team.name + '". Id: ' + team.id)
        }

        // Update answers index.
        for (const answer of updates.answers) {
            this.lastSeenAnswersUpdateId = Math.max(this.lastSeenAnswersUpdateId, answer.update_id)
            if (!this.answersIndex.has(answer.question)) {
                this.answersIndex.set(answer.question, new Map())
            }
            this.answersIndex.get(answer.question).set(answer.team_id, answer)
            console.log('Answer update. Question: ' + answer.question +
                '. Team Id: ' + answer.team_id + '. Answer: "' + answer.answer + '"')
        }

        this.updateResultsTable()
        this.updateAnswersTable()
        this.highlightQuestionHeader()
    }

    async listenToServer() {
        var failedAttempts = 0
        while (failedAttempts < 60) {
            var updates = null
            try {
                updates = null
                updates = await this.api.getUpdates(
                    this.lastSeenStatusUpdateId + 1,
                    this.lastSeenTeamsUpdateId + 1,
                    this.lastSeenAnswersUpdateId + 1
                )

                failedAttempts = 0
            } catch (error) {
                failedAttempts++
                console.error('Could not get updates: ' + error)
                await new Promise(r => setTimeout(r, 1000));
            }
            if (updates != null) {
                this.updateQuiz(updates)
            }
        }
        console.error('Gave up after ' + failedAttempts + ' failed attempts.')
    }
}

if (typeof (window) !== 'undefined') {
    window.onload = () => {
        const api = new Api(fetch.bind(window))
        const controller = new QuizController(document, api)
        controller.init()
        controller.listenToServer()
    }
}
