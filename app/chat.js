window.onload = function() {
    checkSession()
}

async function checkSession() {
    try {
        const response = await fetch('http://127.0.0.1:5000/check-session', {
            credentials: 'include'
        })
        const data = await response.json()

        if (!data.logged_in) {
            window.location.href = 'http://127.0.0.1:5000'
        } else {
            document.getElementById('user-email').textContent = data.email
            const roleBadge = document.getElementById('user-role')
            roleBadge.textContent = data.role.toUpperCase()
            roleBadge.className   = `role-badge role-${data.role}`

            if (data.role === 'admin') {
                document.getElementById('add-record-btn').style.display = 'block'
            }

            // Load notifications for both roles
            loadNotifications()

            // Show popup for both admin and viewer
            showDefectPopup()
        }
    } catch (err) {
        window.location.href = 'http://127.0.0.1:5000'
    }
}

async function loadNotifications() {
    try {
        const response = await fetch('http://127.0.0.1:5000/notifications', {
            credentials: 'include'
        })
        const data = await response.json()

        // Update bell count
        const total = data.high_count + data.medium_count
        const badge = document.getElementById('notif-count')
        badge.textContent = total
        badge.style.background = data.high_count > 0 ? '#EF4444' : '#F59E0B'

        // Fill HIGH risk list
        const highList = document.getElementById('notif-high')
        highList.innerHTML = ''
        if (data.high_risk.length === 0) {
            highList.innerHTML = '<p class="notif-empty">No HIGH risk equipment this month</p>'
        } else {
            data.high_risk.forEach(item => {
                highList.innerHTML += `
                    <div class="notif-item high">
                        <div class="notif-equip">${item.equipment}</div>
                        <div class="notif-detail">
                            Expected: ${item.predicted_date} (${item.avg_days} days)
                        </div>
                    </div>`
            })
        }

        // Fill MEDIUM risk list
        const medList = document.getElementById('notif-medium')
        medList.innerHTML = ''
        if (data.medium_risk.length === 0) {
            medList.innerHTML = '<p class="notif-empty">No MEDIUM risk equipment this month</p>'
        } else {
            data.medium_risk.forEach(item => {
                medList.innerHTML += `
                    <div class="notif-item medium">
                        <div class="notif-equip">${item.equipment}</div>
                        <div class="notif-detail">
                            Expected: ${item.predicted_date} (${item.avg_days} days)
                        </div>
                    </div>`
            })
        }

    } catch (err) {
        console.log('Notification load error:', err)
    }
}

async function showDefectPopup() {
    try {
        const response = await fetch('http://127.0.0.1:5000/notifications', {
            credentials: 'include'
        })
        const data = await response.json()

        if (data.high_count === 0) return

        // Build popup content
        let content = `<p style="margin-bottom:12px; color:#6B7280; font-size:13px;">
            ${data.high_count} equipment at HIGH risk this month:</p>`

        data.high_risk.slice(0, 5).forEach(item => {
            content += `
                <div class="popup-item">
                    <span class="popup-risk-badge">HIGH</span>
                    <div>
                        <div class="popup-equip">${item.equipment}</div>
                        <div class="popup-date">Expected: ${item.predicted_date}</div>
                    </div>
                </div>`
        })

        if (data.high_count > 5) {
            content += `<p style="color:#6B7280; font-size:12px; margin-top:8px;">
                +${data.high_count - 5} more. Click 🔔 to see all.</p>`
        }

        document.getElementById('popup-month').textContent  = data.month
        document.getElementById('popup-content').innerHTML  = content
        document.getElementById('admin-popup').style.display = 'block'

    } catch (err) {
        console.log('Popup error:', err)
    }
}

function toggleNotifications() {
    const panel = document.getElementById('notif-panel')
    panel.style.display = panel.style.display === 'block' ? 'none' : 'block'
}

function switchTab(tab) {
    document.getElementById('notif-high').style.display   = tab === 'high'   ? 'block' : 'none'
    document.getElementById('notif-medium').style.display = tab === 'medium' ? 'block' : 'none'

    document.querySelectorAll('.notif-tab').forEach((btn, i) => {
        btn.classList.toggle('active', (tab === 'high' && i === 0) || (tab === 'medium' && i === 1))
    })
}

function closePopup() {
    document.getElementById('admin-popup').style.display = 'none'
}

async function sendMessage() {
    const input   = document.getElementById('chat-input')
    const sendBtn = document.getElementById('send-btn')
    const message = input.value.trim()

    if (!message) return

    addMessage(message, 'user')
    input.value      = ''
    sendBtn.disabled = true
    showTyping()

    // Check for monthly query locally
    const monthNames = ['january','february','march','april','may','june',
                        'july','august','september','october','november','december']
    const upcomingMatch = message.toLowerCase().match(/(\d+)\s*month/)
    const monthMatch    = monthNames.find(m => message.toLowerCase().includes(m))

    if (upcomingMatch) {
        const months = parseInt(upcomingMatch[1])
        removeTyping()
        await showUpcomingDefects(months)
        sendBtn.disabled = false
        return
    }

    if (monthMatch) {
        const monthNum = monthNames.indexOf(monthMatch) + 1
        removeTyping()
        await showMonthlyDefects(monthNum)
        sendBtn.disabled = false
        return
    }

    const slowWarning = setTimeout(() => {
        const messages = document.getElementById('chat-messages')
        const warning  = document.createElement('div')
        warning.id     = 'slow-warning'
        warning.style  = 'text-align:center; color:#6B7280; font-size:12px; padding:4px;'
        warning.textContent = '⏳ AI is thinking... this may take 30-60 seconds'
        messages.appendChild(warning)
    }, 5000)

    try {
        const response = await fetch('http://127.0.0.1:5000/api/chat', {
            method     : 'POST',
            headers    : { 'Content-Type': 'application/json' },
            credentials: 'include',
            body       : JSON.stringify({ message })
        })

        const data = await response.json()
        clearTimeout(slowWarning)
        const warn = document.getElementById('slow-warning')
        if (warn) warn.remove()
        removeTyping()

        if (data.redirect) {
            addMessage(data.reply, 'bot')
            setTimeout(() => {
                window.location.href = `http://127.0.0.1:5000${data.redirect}`
            }, 1500)
        } else if (data.error) {
            window.location.href = 'http://127.0.0.1:5000'
        } else {
            addMessage(data.reply, 'bot')
        }

    } catch (err) {
        clearTimeout(slowWarning)
        removeTyping()
        addMessage('Server error. Please try again.', 'bot')
    }

    sendBtn.disabled = false
}

async function showUpcomingDefects(months) {
    try {
        const response = await fetch(`http://127.0.0.1:5000/upcoming-defects?months=${months}`, {
            credentials: 'include'
        })
        const data = await response.json()

        if (data.total === 0) {
            addMessage(`No defects predicted in the next ${months} months.`, 'bot')
            return
        }

        let msg = `Upcoming defects in next ${months} month(s) — ${data.total} equipment at risk:\n\n`
        data.defects.slice(0, 10).forEach(item => {
            msg += `${item.risk === 'HIGH' ? '🔴' : '🟡'} ${item.equipment}\n`
            msg += `   Expected: ${item.predicted_date} (${item.avg_days} days)\n\n`
        })

        if (data.total > 10) {
            msg += `...and ${data.total - 10} more. Click 🔔 for full list.`
        }

        addMessage(msg, 'bot')

    } catch (err) {
        addMessage('Error loading upcoming defects.', 'bot')
    }
}

async function showMonthlyDefects(monthNum) {
    const monthNames = ['January','February','March','April','May','June',
                        'July','August','September','October','November','December']
    const year = new Date().getFullYear()

    try {
        const response = await fetch(
            `http://127.0.0.1:5000/monthly-defects?month=${monthNum}&year=${year}`,
            { credentials: 'include' }
        )
        const data = await response.json()

        if (data.total === 0) {
            addMessage(`No defects predicted for ${monthNames[monthNum-1]} ${year}.`, 'bot')
            return
        }

        let msg = `Predicted defects for ${monthNames[monthNum-1]} ${year} — ${data.total} equipment:\n\n`
        data.defects.slice(0, 10).forEach(item => {
            msg += `${item.risk === 'HIGH' ? '🔴' : '🟡'} ${item.equipment}\n`
            msg += `   Expected: ${item.predicted_date} (${item.avg_days} days)\n\n`
        })

        if (data.total > 10) {
            msg += `...and ${data.total - 10} more. Click 🔔 for full list.`
        }

        addMessage(msg, 'bot')

    } catch (err) {
        addMessage('Error loading monthly defects.', 'bot')
    }
}

function addMessage(text, sender) {
    const messages   = document.getElementById('chat-messages')
    const messageDiv = document.createElement('div')
    messageDiv.className = `message ${sender}`

    const avatar = document.createElement('div')
    avatar.className   = `message-avatar ${sender}-avatar`
    avatar.textContent = sender === 'bot' ? '⚡' : '👤'

    const bubble = document.createElement('div')
    bubble.className = `message-bubble ${sender}-bubble`

    const cleanText = text
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/#{1,6} /g, '')

    bubble.style.whiteSpace = 'pre-wrap'
    bubble.textContent      = cleanText

    messageDiv.appendChild(avatar)
    messageDiv.appendChild(bubble)
    messages.appendChild(messageDiv)
    messages.scrollTop = messages.scrollHeight
}

function showTyping() {
    const messages   = document.getElementById('chat-messages')
    const typing     = document.createElement('div')
    typing.className = 'message bot'
    typing.id        = 'typing-indicator'
    typing.innerHTML = `
        <div class="message-avatar bot-avatar">⚡</div>
        <div class="message-bubble bot-bubble">
            <div class="typing">
                <span></span><span></span><span></span>
            </div>
        </div>`
    messages.appendChild(typing)
    messages.scrollTop = messages.scrollHeight
}

function removeTyping() {
    const typing = document.getElementById('typing-indicator')
    if (typing) typing.remove()
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        sendMessage()
    }
}

async function logout() {
    await fetch('http://127.0.0.1:5000/logout', {
        method     : 'POST',
        credentials: 'include'
    })
    window.location.href = 'http://127.0.0.1:5000'
}