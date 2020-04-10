function addTableRow(table, values) {
    var tr = document.createElement('tr')
    for (i in values) {
        value = values[i]

        if (value instanceof HTMLElement) {
            tr.appendChild(document.createElement('td')).appendChild(value)
        } else {
            tr.appendChild(document.createElement('td')).innerHTML = value
        }
    }
    table.appendChild(tr)
}

function updateStatusTable(status) {
    var table = document.getElementById('status')
    table.innerHTML = ''
    addTableRow(table, ["OK", status.ok])
    addTableRow(table, ["Quiz", status.quiz_id])
    addTableRow(table, ["Question", status.question_id])
    addTableRow(table, ["Registration", status.is_registration])
    addTableRow(table, ["Last updated", new Date()])
}

function updateTeamsTable(status) {
    var table = document.getElementById('teams')
    table.innerHTML = ''
    for (chat_id in status.teams) {
        addTableRow(table, [status.teams[chat_id], chat_id])
    }
}

function updateAnswersTable(status) {
    var table = document.getElementById('answers')
    table.innerHTML = ''
    team_ids = Object.keys(status.teams);
    teams_array = team_ids.map(function (id) {
        return status.teams[id]
    })

    question_set = status.question_set.sort()
    addTableRow(table, ['', ''].concat(teams_array))
    for (const i in question_set) {
        let question_id = question_set[i];
        answers = team_ids.map(function (id) {
            if (question_id in status.answers && id in status.answers[question_id]) {
                return status.answers[question_id][id]
            } else {
                return ''
            }
        })

        startButton = document.createElement('button')
        startButton.innerHTML = 'Start'
        startButton.onclick = function () {
            sendCommand({ "command": "start_question", "question_id": question_id }, function (response) {
                console.log("Question '" + question_id + "' started!")
            }, function (error) {
                console.log("Could not start question: " + error)
            })
        }

        addTableRow(table, [startButton, question_id].concat(answers))
    }
}

function sendCommand(command, callback, error_callback) {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
            var response = JSON.parse(this.responseText);
            if (this.status != 200) {
                console.warn('Status code: ' + this.status)
                error_callback(response.error)
            } else {
                callback(response);
            }
        }
    }
    xhttp.open("POST", "/", true);
    xhttp.setRequestHeader("Content-type", "application/json");
    xhttp.send(JSON.stringify(command));
}

function getStatus() {
    sendCommand({ "command": "get_status" }, function (response) {
        updateStatusTable(response)
        updateTeamsTable(response)
        updateAnswersTable(response)
    }, function (error) {
        console.log('Could not get status: ' + error)
    })
}

function startRegistration() {
    sendCommand({ "command": "start_registration" }, function (response) {
        console.log('Registration started!')
    }, function (error) {
        console.warn('Could not start registration: ' + error)
    })
}

function stopRegistration() {
    sendCommand({ "command": "stop_registration" }, function (response) {
        console.log('Registration stopped!')
    }, function (error) {
        console.warn('Could not stop registration: ' + error)
    })
}

function stopQuestion() {
    sendCommand({ "command": "stop_question" }, function (response) {
        console.log('Question stopped!')
    }, function (error) {
        console.warn('Could not stop question: ' + error)
    })
}

function onLoad() {
    setInterval(getStatus, 1000)
}
