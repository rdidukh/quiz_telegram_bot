export class Api {
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

    async startQuestion(question) {
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

    async setAnswerPoints(question, teamId, points) {
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

    async sendResults(teamId) {
        await this.callServer('sendResults', {
            'team_id': teamId,
        })
    }
}
