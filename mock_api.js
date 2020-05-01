export class MockApi {
    constructor() {
        this.getUpdatesCalls = []
        this.mockGetUpdates = async () => { }
        this.sendResultsCalls = []
        this.mockSendResults = async () => { }
        this.startRegistrationCalls = []
        this.mockStartRegistration = async () => { }
        this.stopRegistrationCalls = []
        this.mockStopRegistration = async () => { }
        this.startQuestionCalls = []
        this.mockStartQuestion = async () => { }
        this.stopQuestionCalls = []
        this.mockStopQuestion = async () => { }
        this.setAnswerPointsCalls = []
        this.mockSetAnswerPoints = async () => { }
    }

    async getUpdates(a, b, c) {
        this.getUpdatesCalls.push([a, b, c])
        return this.mockGetUpdates(a, b, c)
    }

    async sendResults(t) {
        this.sendResultsCalls.push([t])
        return this.mockSendResults(t)
    }

    async startRegistration() {
        this.startRegistrationCalls.push([])
        return this.mockStartRegistration()
    }

    async stopRegistration() {
        this.stopRegistrationCalls.push([])
        return this.mockStopRegistration()
    }

    async startQuestion(q) {
        this.startQuestionCalls.push([q])
        return this.mockStartQuestion(q)
    }

    async stopQuestion() {
        this.stopQuestionCalls.push([])
        return this.mockStopQuestion()
    }

    async setAnswerPoints(q, t, p) {
        this.setAnswerPointsCalls.push([q, t, p])
        return this.mockSetAnswerPoints(q, t, p)
    }
}
