const correctAnswerButtonText = '\u2714' // ✔
const wrongAnswerButtonText = '\u2716' // ✖

type Fetcher = (info: RequestInfo, init: RequestInit) => Promise<Response>
type Command = 'getUpdates' | 'startRegistration' | 'stopRegistration' | 'startQuestion' | 'stopQuestion' | 'setAnswerPoints';

export interface Status {
    update_id: number
    quiz_id: string
    language: string
    question?: number
    time: string
    registration: boolean
}

export interface Team {
    update_id: number
    id: number
    name: string
}

export interface Answer {
    update_id: number
    question: number
    team_id: number
    answer: string
    points?: number
}

export interface Updates {
    status?: Status
    teams: Array<Team>
    answers: Array<Answer>
}

export class Api {
    constructor(private fetcher: Fetcher) {
        this.fetcher = fetcher
    }

    private async callServer(command: Command, args = {}): Promise<any> {
        const response = await this.fetcher('/api/' + command, {
            method: 'POST',
            body: JSON.stringify(args),
            headers: { 'Content-Type': 'application/json' },
        })

        const text = await response.text()

        let data: any
        try {
            let data = JSON.parse(text)
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

    async getUpdates(minStatusUpdateId: number, minTeamsUpdateId: number, minAnswersUpdateId: number): Promise<Updates> {
        const response = await this.callServer('getUpdates', {
            min_status_update_id: minStatusUpdateId,
            min_teams_update_id: minTeamsUpdateId,
            min_answers_update_id: minAnswersUpdateId,
            timeout: 30,
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

    async startQuestion(question: number) {
        try {
            await this.callServer('startQuestion', { question: question })
            console.log('Question ' + question + ' started!')
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

    async setAnswerPoints(question: number, teamId: number, points: number) {
        try {
            await this.callServer('setAnswerPoints', {
                'question': question,
                'team_id': teamId,
                'points': points,
            })
            console.log('Points for answer to question ' + question + ' of team ' + teamId + ' set to ' + points)
        } catch (error) {
            console.warn('Could not set answer points for question ' + question + ' of team ' + teamId + ': ' + error)
        }
    }
}

function updateTextContent(element: HTMLElement, newTextContent: string) {
    if (element.textContent !== newTextContent) {
        element.textContent = newTextContent
    }
}

export class QuizController {
    numberOfQuestions: number
    // teamId -> Team.
    teamsIndex: Map<number, Team>
    // question -> teamId -> Answer
    answersIndex: Map<number, Map<number, Answer>>
    currentQuestion: number
    lastSeenStatusUpdateId: number
    lastSeenTeamsUpdateId: number
    lastSeenAnswersUpdateId: number

    constructor(private document: Document, private api: Api) {
        this.document = document
        this.api = api
        this.numberOfQuestions = 24
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
            let question = this.currentQuestion - 1
            if (question <= 0) {
                question = this.numberOfQuestions
            }
            this.showAnswersForQuestion(question)
        }

        this.document.getElementById('next_question_button').onclick = async () => {
            let question = this.currentQuestion + 1
            if (question > this.numberOfQuestions) {
                question = 1
            }
            this.showAnswersForQuestion(question)
        }
    }

    updateStatusTable(status: Status) {
        const table = this.document.getElementById('status_table') as HTMLTableElement
        let question = ''
        if (status.question != null) {
            question = status.question.toString()
        }
        updateTextContent(table.rows[0].cells[1], status.quiz_id)
        updateTextContent(table.rows[1].cells[1], status.language)
        updateTextContent(table.rows[2].cells[1], question)
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
        const table = this.document.getElementById('results_table') as HTMLTableElement
        const resultsTableHeaderRow = table.insertRow()
        resultsTableHeaderRow.insertCell().textContent = 'Team'
        resultsTableHeaderRow.insertCell().textContent = 'Total'

        for (let question = 1; question <= this.numberOfQuestions; question++) {
            resultsTableHeaderRow.insertCell().textContent = question.toString()
        }
    }

    updateResultsTable() {
        const table = this.document.getElementById('results_table') as HTMLTableElement

        for (const [teamId, team] of this.teamsIndex) {
            const rowId = 'results_team_' + teamId + '_row'
            let row = this.document.getElementById(rowId) as HTMLTableRowElement
            if (!row) {
                row = table.insertRow()
                row.id = rowId

                row.insertCell()
                row.insertCell()
                for (let q = 1; q <= this.numberOfQuestions; q++) {
                    row.insertCell()
                }
            }

            let totalPoints = 0
            let points: number = null

            for (let question = 1; question <= this.numberOfQuestions; question++) {
                if (this.answersIndex.has(question)) {
                    const answers = this.answersIndex.get(question)
                    if (answers.has(teamId)) {
                        points = answers.get(teamId).points
                    }
                }

                if (points != null) {
                    totalPoints += points
                    updateTextContent(row.cells[question + 1], points.toString())
                }
            }

            updateTextContent(row.cells[0], team.name)
            updateTextContent(row.cells[1], totalPoints.toString())
        }
    }

    showAnswersForQuestion(question: number) {
        this.currentQuestion = question
        this.document.getElementById('question_span').textContent = question.toString()
        this.updateAnswersTable()
    }

    updateStartStopQuestionButtons(status: Status) {
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
        const table = this.document.getElementById('answers_table') as HTMLTableElement

        let answers = new Map<number, Answer>()
        if (this.answersIndex.has(this.currentQuestion)) {
            let answers = this.answersIndex.get(this.currentQuestion)
        }

        for (const [teamId, team] of this.teamsIndex) {
            const rowId = 'answers_team_' + teamId + '_row'
            let row = this.document.getElementById(rowId) as HTMLTableRowElement
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

            let answer = ''
            let points: number = null
            if (answers.has(teamId)) {
                answer = answers.get(teamId).answer
                points = answers.get(teamId).points
            }

            let cellClass: string
            if (points == null) {
                let cellClass = 'missing_answer'
            } else if (points > 0) {
                let cellClass = 'correct_answer'
            } else if (points <= 0) {
                let cellClass = 'wrong_answer'
            }

            updateTextContent(row.cells[0], team.name)
            updateTextContent(row.cells[1], answer)
            row.cells[1].classList.remove('correct_answer', 'wrong_answer', 'missing_answer')
            row.cells[1].classList.add(cellClass)
        }
    }

    updateQuiz(updates: Updates) {
        if (updates.status) {
            this.lastSeenStatusUpdateId = updates.status.update_id
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
    }

    async listenToServer() {
        var failedAttempts = 0
        while (failedAttempts < 60) {
            let updates: Updates = null
            try {
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

function onLoad() {
    const api = new Api(fetch.bind(window))
    const controller = new QuizController(document, api)
    controller.init()
    controller.listenToServer()
}
