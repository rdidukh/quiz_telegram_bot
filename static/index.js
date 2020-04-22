const correctAnswerButtonText = '\u2714' // ✔
const wrongAnswerButtonText = '\u2716' // ✖

class Api {
    constructor(fetcher) {
        this.fetcher = fetcher
    }

    async callServer(command, args = {}) {
        const response = await this.fetcher('/api/' + command, {
            method: 'POST',
            body: JSON.stringify(args),
            headers: { 'Content-Type': 'application/json' },
        })

        const text = await response.text()

        try {
            var data = JSON.parse(text)
        } catch (e) {
            console.error('Response is not a valid JSON object.')
            console.log(text)
            throw 'Response is not a valid JSON object.'
        }

        if (response.status !== 200) {
            throw data.error;
        }

        return data;
    }

    async getUpdates(minStatusUpdateId, minTeamsUpdateId, minAnswersUpdateId) {
        const response = await this.callServer('getUpdates', {
            min_status_update_id: minStatusUpdateId,
            min_teams_update_id: minTeamsUpdateId,
            min_answers_update_id: minAnswersUpdateId,
        })

        return response
    }

    async startRegistration() {
        try {
            await this.callServer('startRegistration')
            console.log('Registration started!')
        } catch (error) {
            console.warn('Could not start registration: ' + error)
        }
    }

    async stopRegistration() {
        try {
            await this.callServer('stopRegistration')
            console.log('Registration stopped!')
        } catch (error) {
            console.warn('Could not stop registration: ' + error)
        }
    }

    async startQuestion(question) {
        try {
            await this.callServer('startQuestion', { question: question })
            console.log('Question ' + question + 'started!')
        } catch (error) {
            console.warn('Could not start question ' + question + ': ' + error)
        }
    }

    async stopQuestion() {
        try {
            await this.callServer('stopQuestion')
            console.log('Question stopped!')
        } catch (error) {
            console.warn('Could not stop question: ' + error)
        }
    }

    async setAnswerPoints(question, teamId, points) {
        try {
            await this.callServer('setAnswerPoints', {
                'question': question,
                'team_id': teamId,
                'points': points,
            })
            console.log('Answer points for question ' + question + ' of team ' + teamId + ' set to ' + points)
        } catch (error) {
            console.warn('Could not set answer points for question ' + question + ' of team ' + teamId + ': ' + error)
        }
    }
}

function updateTextContent(element, newTextContent) {
    if (element.textContent != newTextContent) {
        element.textContent = newTextContent
    }
}

class QuizController {
    constructor(document, api) {
        this.document = document
        this.api = api
        this.numberOfQuestions = 30
        // teamId -> Team.
        this.teamsIndex = new Map()
        // question -> teamId -> Answer
        this.answersIndex = new Map()
        this.currentQuestion = 1
        this.lastSeenStatusUpdateId = 0
        this.lastSeenTeamsUpdateId = 0
        this.lastSeenAnswersUpdateId = 0
    }

    init() {
        this.initResultsTable()
    }

    updateStatusTable(status) {
        const table = this.document.getElementById('status_table')
        updateTextContent(table.rows[0].cells[1], status.quiz_id)
        updateTextContent(table.rows[1].cells[1], status.language)
        updateTextContent(table.rows[2].cells[1], status.question)
        updateTextContent(table.rows[3].cells[1], status.registration.toString())
        updateTextContent(table.rows[4].cells[1], status.time)
    }

    initResultsTable() {
        const table = this.document.getElementById('results_table')
        const resultsTableHeaderRow = table.insertRow(0)
        resultsTableHeaderRow.insertCell(-1)
        resultsTableHeaderRow.insertCell(-1).textContent = 'Total'

        const resultsStartQuestionRow = table.insertRow(-1)
        resultsStartQuestionRow.insertCell(-1)
        resultsStartQuestionRow.insertCell(-1)

        const showAnswersRow = table.insertRow(-1)
        showAnswersRow.insertCell(-1)
        showAnswersRow.insertCell(-1)

        for (let question = 1; question <= this.numberOfQuestions; question++) {
            resultsTableHeaderRow.insertCell(-1).textContent = question
            const startQuestionButton = this.document.createElement('button')
            startQuestionButton.textContent = '>'
            startQuestionButton.onclick = () => { this.api.startQuestion(question) }

            const showAnswersButton = this.document.createElement('button')
            showAnswersButton.textContent = 'A'
            showAnswersButton.onclick = async () => { this.showAnswersForQuestion(question) }

            resultsStartQuestionRow.insertCell(-1).appendChild(startQuestionButton)
            showAnswersRow.insertCell(-1).appendChild(showAnswersButton)
        }
    }

    updateResultsTable() {
        const table = this.document.getElementById('results_table')

        for (const [teamId, team] of this.teamsIndex) {
            const rowId = 'results_team_' + teamId + '_row'
            var row = this.document.getElementById(rowId)
            if (!row) {
                row = table.insertRow(-1)
                row.id = rowId

                row.insertCell(-1)
                row.insertCell(-1)
                for (let q = 1; q <= this.numberOfQuestions; q++) {
                    row.insertCell(-1).textContent = '0'
                }
            }
            updateTextContent(row.cells[0], team.name)
        }
    }

    showAnswersForQuestion(question) {
        this.currentQuestion = question
        this.document.querySelector('#answers_header span').textContent = question
        this.updateAnswersTable()
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
                row = table.insertRow(-1)
                row.id = rowId

                const correctButton = this.document.createElement('button')
                correctButton.textContent = correctAnswerButtonText
                correctButton.classList.add('correct_button')
                correctButton.onclick = async () => {
                    this.api.setAnswerPoints(this.currentQuestion, teamId, 1)
                }

                const wrongButton = this.document.createElement('button')
                wrongButton.textContent = wrongAnswerButtonText
                wrongButton.classList.add('wrong_button')
                wrongButton.onclick = async () => {
                    this.api.setAnswerPoints(this.currentQuestion, teamId, 0)
                }

                row.insertCell(-1).textContent = team.name
                row.insertCell(-1) // Answer.
                row.insertCell(-1).appendChild(correctButton)
                row.insertCell(-1).appendChild(wrongButton)
            }

            if (!answers.has(teamId)) {
                // No answer to the question for this team.
                var answer = { text: '', points: null }
            } else {
                var answer = answers.get(teamId)
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
            console.log('Status update received. update_id: ' + updates.status.update_id)
            this.updateStatusTable(updates.status)
        }

        // Update teams index.
        for (const team of updates.teams) {
            this.lastSeenTeamsUpdateId = Math.max(this.lastSeenTeamsUpdateId, team.update_id)
            this.teamsIndex.set(team.id, team)
            console.log('Team update received. Name: "' + team.name + '". Id: ' + team.id)
        }

        // Update answers index.
        for (const answer of updates.answers) {
            this.lastSeenAnswersUpdateId = Math.max(this.lastSeenAnswersUpdateId, answer.update_id)
            if (!this.answersIndex.has(answer.question)) {
                this.answersIndex.set(answer.question, new Map())
            }
            this.answersIndex.get(answer.question).set(answer.team_id, answer)
            console.log('Answer update received. Question: ' + answer.question +
                '. Team Id: ' + answer.team_id + '. Answer: "' + answer.answer + '"')
        }

        this.updateResultsTable()
        this.updateAnswersTable()
    }

    getUpdates() {
        this.api.getUpdates(
            this.lastSeenStatusUpdateId + 1,
            this.lastSeenTeamsUpdateId + 1,
            this.lastSeenAnswersUpdateId + 1
        ).then((updates) => {
            this.updateQuiz(updates)
        })
    }

    listenToServer() {
        setInterval(this.getUpdates.bind(this), 1000)
    }
}

var api = null

function onLoad() {
    api = new Api(fetch.bind(window))
    const controller = new QuizController(document, api)
    controller.init()
    controller.listenToServer()
}

if (typeof window === 'undefined') {
    module.exports = {
        Api: Api,
        QuizController: QuizController,
    }
}
