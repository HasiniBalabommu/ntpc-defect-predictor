async function loginAdmin() {
    const email    = document.getElementById('admin-email').value.trim()
    const password = document.getElementById('admin-password').value.trim()
    const errorMsg = document.getElementById('admin-error')

    errorMsg.textContent = ''

    if (!email || !password) {
        errorMsg.textContent = 'Please fill in all fields'
        return
    }

    const btn = document.querySelector('.admin-btn')
    btn.disabled    = true
    btn.textContent = 'Logging in...'

    try {
        const response = await fetch('http://127.0.0.1:5000/login', {
            method     : 'POST',
            headers    : { 'Content-Type': 'application/json' },
            credentials: 'include',
            body       : JSON.stringify({ email, password, role: 'admin' })
        })

        const data = await response.json()

        if (data.success && data.role === 'admin') {
            window.location.href = 'http://127.0.0.1:5000/chat-page'
        } else if (data.success && data.role !== 'admin') {
            errorMsg.textContent = 'This email is not registered as admin'
        } else {
            errorMsg.textContent = data.message
        }

    } catch (err) {
        errorMsg.textContent = 'Server not reachable. Make sure server.py is running.'
    }

    btn.disabled    = false
    btn.textContent = 'Login as Admin'
}

async function loginViewer() {
    const email    = document.getElementById('viewer-email').value.trim()
    const password = document.getElementById('viewer-password').value.trim()
    const errorMsg = document.getElementById('viewer-error')

    errorMsg.textContent = ''

    if (!email || !password) {
        errorMsg.textContent = 'Please fill in all fields'
        return
    }

    const btn = document.querySelector('.viewer-btn')
    btn.disabled    = true
    btn.textContent = 'Logging in...'

    try {
        const response = await fetch('http://127.0.0.1:5000/login', {
            method     : 'POST',
            headers    : { 'Content-Type': 'application/json' },
            credentials: 'include',
            body       : JSON.stringify({ email, password, role: 'viewer' })
        })

        const data = await response.json()

        if (data.success && data.role === 'viewer') {
            window.location.href = 'http://127.0.0.1:5000/chat-page'
        } else if (data.success && data.role !== 'viewer') {
            errorMsg.textContent = 'This email is not registered as viewer'
        } else {
            errorMsg.textContent = data.message
        }

    } catch (err) {
        errorMsg.textContent = 'Server not reachable. Make sure server.py is running.'
    }

    btn.disabled    = false
    btn.textContent = 'Login as Viewer'
}

// Enter key support
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        const focused = document.activeElement.id
        if (focused.includes('admin')) loginAdmin()
        if (focused.includes('viewer')) loginViewer()
    }
})