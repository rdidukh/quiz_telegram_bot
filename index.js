function addTableRow(table, values) {
    var tr = document.createElement('tr')
    for (i in values) {
        tr.appendChild(document.createElement('td')).innerHTML = values[i]
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
    teams_array = team_ids.map(function(id){
        return status.teams[id]
    })

    question_set = status.question_set.sort()
    addTableRow(table, [' '].concat(teams_array))
    for (i in question_set) {
        question_id = question_set[i];
        answers = team_ids.map(function(id) {
            if (question_id in status.answers) {
                return status.answers[question_id][id]
            } else {
                return ''
            }
        })
        addTableRow(table, [question_id].concat(answers))
    }
}

function getStatus() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4) {
            if (this.status != 200) {
                console.warn('Status code: ' + this.status)
                console.log(this.responseText)
            } else {
                var response = JSON.parse(this.responseText);
                updateStatusTable(response)
                updateTeamsTable(response)
                updateAnswersTable(response)
            }
        }
    };
    xhttp.open("POST", "/", true);
    xhttp.setRequestHeader("Content-type", "application/json");
    xhttp.send('{"command": "get_status"}');
}
