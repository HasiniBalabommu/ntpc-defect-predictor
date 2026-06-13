let currentEditId = null

window.onload = function() {
    checkSession()
    loadTrainingStatus()
    loadRecentRecords()
    loadRecentUploads()
}

async function checkSession() {
    try {
        const response = await fetch('http://127.0.0.1:5000/check-session', {
            credentials: 'include'
        })
        const data = await response.json()

        if (!data.logged_in) {
            window.location.href = 'http://127.0.0.1:5000'
            return
        }

        if (data.role !== 'admin') {
            alert('Access denied! Only admins can add records.')
            window.location.href = 'http://127.0.0.1:5000/chat-page'
            return
        }

        document.getElementById('user-email').textContent = data.email
        const roleBadge = document.getElementById('user-role')
        roleBadge.textContent = data.role.toUpperCase()
        roleBadge.className   = `role-badge role-${data.role}`

    } catch (err) {
        window.location.href = 'http://127.0.0.1:5000'
    }
}

async function submitRecord() {
    const errorMsg   = document.getElementById('error-msg')
    const successMsg = document.getElementById('success-msg')
    errorMsg.textContent   = ''
    successMsg.textContent = ''

    const record = {
        equipment      : document.getElementById('equipment').value.trim(),
        notif_date     : document.getElementById('notif_date').value,
        notif_time     : document.getElementById('notif_time').value,
        priority       : document.getElementById('priority').value,
        notif_type     : document.getElementById('notif_type').value,
        functional_loc : document.getElementById('functional_loc').value.trim(),
        completion_date: document.getElementById('completion_date').value,
        completion_time: document.getElementById('completion_time').value,
        description    : document.getElementById('description').value.trim()
    }

    // Validate all fields
    for (const [key, value] of Object.entries(record)) {
        if (!value) {
            errorMsg.textContent = `Please fill in all fields — ${key.replace(/_/g, ' ')} is empty`
            return
        }
    }

    // Validate completion date
    if (record.completion_date < record.notif_date) {
        errorMsg.textContent = 'Completion date cannot be before notification date'
        return
    }

    const btn = document.querySelector('.submit-btn')
    btn.disabled    = true
    btn.textContent = 'Saving...'

    try {
        const response = await fetch('http://127.0.0.1:5000/add-record', {
            method     : 'POST',
            headers    : { 'Content-Type': 'application/json' },
            credentials: 'include',
            body       : JSON.stringify(record)
        })

        const data = await response.json()

        if (data.success) {
            successMsg.textContent = `✅ Record saved! ${data.new_records}/50 records until next retrain.`
            resetForm()
            loadTrainingStatus()
            loadRecentRecords()
        } else {
            errorMsg.textContent = data.message
        }

    } catch (err) {
        errorMsg.textContent = 'Server error. Please try again.'
    }

    btn.disabled    = false
    btn.textContent = 'Submit Record'
}

async function loadRecentRecords() {
    try {
        const response = await fetch('http://127.0.0.1:5000/recent-records', {
            credentials: 'include'
        })
        const data = await response.json()
        const list = document.getElementById('recent-records-list')

        if (data.records.length === 0) {
            list.innerHTML = '<p style="color:#6B7280; font-size:13px;">No records added yet.</p>'
            return
        }

        list.innerHTML = ''

        data.records.forEach(record => {
            const row = document.createElement('div')
            row.style = 'display:flex; justify-content:space-between; align-items:center; padding:12px; background:#F0F9FF; border-radius:8px; margin-bottom:8px; border:1px solid #BAE6FD;'
            row.innerHTML = `
                <div>
                    <div style="font-weight:600; color:#023E8A; font-size:14px;">
                        ${record.equipment}
                    </div>
                    <div style="color:#6B7280; font-size:12px;">
                        ${record.notif_date} | ${record.priority} | Added: ${record.added_on}
                    </div>
                </div>
                <div style="display:flex; gap:8px;">
                    <button onclick="openEdit(${record.id}, '${record.equipment}', '${record.priority}')"
                        style="background:#0077B6; color:white; border:none; border-radius:6px; 
                               padding:6px 12px; cursor:pointer; font-size:12px;">
                        ✏️ Edit
                    </button>
                    <button onclick="deleteRecord(${record.id})"
                        style="background:#EF4444; color:white; border:none; border-radius:6px; 
                               padding:6px 12px; cursor:pointer; font-size:12px;">
                        🗑️ Delete
                    </button>
                </div>
            `
            list.appendChild(row)
        })

    } catch (err) {
        document.getElementById('recent-records-list').innerHTML =
            '<p style="color:#EF4444; font-size:13px;">Error loading records.</p>'
    }
}

async function deleteRecord(id) {
    if (!confirm('Are you sure you want to delete this record?')) return

    try {
        const response = await fetch(`http://127.0.0.1:5000/delete-record/${id}`, {
            method     : 'DELETE',
            credentials: 'include'
        })
        const data = await response.json()

        if (data.success) {
            loadRecentRecords()
            loadTrainingStatus()
        }
    } catch (err) {
        alert('Error deleting record')
    }
}

function openEdit(id, equipment, priority) {
    currentEditId = id
    document.getElementById('edit-equipment').value  = equipment
    document.getElementById('edit-priority').value   = priority
    document.getElementById('edit-description').value = ''
    document.getElementById('edit-modal').style.display = 'block'
}

function closeEdit() {
    currentEditId = null
    document.getElementById('edit-modal').style.display = 'none'
}

async function saveEdit() {
    const equipment   = document.getElementById('edit-equipment').value.trim()
    const priority    = document.getElementById('edit-priority').value
    const description = document.getElementById('edit-description').value.trim()

    if (!equipment) {
        document.getElementById('edit-error').textContent = 'Equipment name cannot be empty'
        return
    }

    try {
        const response = await fetch(`http://127.0.0.1:5000/edit-record/${currentEditId}`, {
            method     : 'PUT',
            headers    : { 'Content-Type': 'application/json' },
            credentials: 'include',
            body       : JSON.stringify({
                equipment,
                priority,
                description,
                notif_date     : '',
                notif_time     : '',
                notif_type     : '',
                functional_loc : '',
                completion_date: '',
                completion_time: ''
            })
        })

        const data = await response.json()

        if (data.success) {
            closeEdit()
            loadRecentRecords()
        }
    } catch (err) {
        document.getElementById('edit-error').textContent = 'Error saving changes'
    }
}

async function loadTrainingStatus() {
    try {
        const response = await fetch('http://127.0.0.1:5000/training-status', {
            credentials: 'include'
        })
        const data = await response.json()

        document.getElementById('last-trained').textContent = data.last_trained
        document.getElementById('records-used').textContent = data.records_used
        document.getElementById('new-records').textContent  = `${data.new_records}/50`

        // Disable retrain button if no new records
        const retrainBtn = document.getElementById('retrain-btn')
        if (data.new_records === 0) {
            retrainBtn.disabled = true
            retrainBtn.textContent = '🔄 Add Records First to Retrain'
        } else {
            retrainBtn.disabled = false
            retrainBtn.textContent = `🔄 Retrain Model Now (${data.new_records} new records)`
        }

    } catch (err) {
        document.getElementById('last-trained').textContent = 'N/A'
        document.getElementById('records-used').textContent = 'N/A'
        document.getElementById('new-records').textContent  = 'N/A'
    }
}

async function triggerRetrain() {
    const btn = document.getElementById('retrain-btn')
    btn.disabled    = true
    btn.textContent = '🔄 Retraining... please wait'

    try {
        const response = await fetch('http://127.0.0.1:5000/retrain', {
            method     : 'POST',
            credentials: 'include'
        })
        const data = await response.json()

        if (data.success) {
            alert('✅ Model retraining started!')
            loadTrainingStatus()
        } else {
            alert(data.message)
            loadTrainingStatus()
        }

    } catch (err) {
        alert('Server error during retraining')
        loadTrainingStatus()
    }
}

function resetForm() {
    document.getElementById('equipment').value       = ''
    document.getElementById('notif_date').value      = ''
    document.getElementById('notif_time').value      = ''
    document.getElementById('priority').value        = ''
    document.getElementById('notif_type').value      = ''
    document.getElementById('functional_loc').value  = ''
    document.getElementById('completion_date').value = ''
    document.getElementById('completion_time').value = ''
    document.getElementById('description').value     = ''
}

function goBack() {
    window.location.href = 'http://127.0.0.1:5000/chat-page'
}

async function logout() {
    await fetch('http://127.0.0.1:5000/logout', {
        method     : 'POST',
        credentials: 'include'
    })
    window.location.href = 'http://127.0.0.1:5000'
}

// ── Excel Upload Functions ──

const REQUIRED_COLUMNS = [
    'Notif.date',
    'equipment',
    'Notif. Time',
    'Completion time',
    'Completn date',
    'Priority',
    'Notifictn type',
    'Functional Loc.'
]

let selectedFile = null

function handleFileSelect(event) {
    const file = event.target.files[0]
    if (file) processFile(file)
}

function handleDragOver(event) {
    event.preventDefault()
    document.getElementById('upload-area').classList.add('dragover')
}

function handleDrop(event) {
    event.preventDefault()
    document.getElementById('upload-area').classList.remove('dragover')
    const file = event.dataTransfer.files[0]
    if (file) processFile(file)
}

function processFile(file) {
    // Check file type
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        document.getElementById('upload-error').textContent = 
            'Only .xlsx or .xls files are allowed'
        return
    }

    selectedFile = file

    // Show file info
    document.getElementById('file-name').textContent = file.name
    document.getElementById('file-info').style.display = 'block'
    document.getElementById('upload-error').textContent = ''
    document.getElementById('upload-success').textContent = ''

    // Validate columns using FileReader
    validateExcelColumns(file)
}

async function validateExcelColumns(file) {
    const formData = new FormData()
    formData.append('file', file)

    try {
        const response = await fetch('http://127.0.0.1:5000/validate-excel', {
            method     : 'POST',
            credentials: 'include',
            body       : formData
        })

        const data = await response.json()

        document.getElementById('validation-result').style.display = 'block'

        if (data.missing_columns && data.missing_columns.length > 0) {
            // Show missing columns
            document.getElementById('missing-cols-box').style.display = 'block'
            document.getElementById('success-box').style.display = 'none'

            let missingHtml = ''
            data.missing_columns.forEach(col => {
                missingHtml += `<span class="missing-col-item">❌ ${col}</span>`
            })
            document.getElementById('missing-cols-list').innerHTML = missingHtml

            // Keep upload button disabled
            document.getElementById('upload-btn').disabled = true

        } else {
            // All columns present
            document.getElementById('missing-cols-box').style.display = 'none'
            document.getElementById('success-box').style.display = 'block'

            document.getElementById('file-stats').innerHTML = `
                <p class="stat-item">✅ All required columns present</p>
                <p class="stat-item">📊 Total rows: ${data.total_rows}</p>
                <p class="stat-item">📋 Total columns: ${data.total_cols}</p>
                <p class="stat-item">📅 Ready to upload and process</p>
            `

            // Enable upload button
            document.getElementById('upload-btn').disabled = false
        }

    } catch (err) {
        document.getElementById('upload-error').textContent = 
            'Error validating file. Please try again.'
    }
}

async function uploadExcel() {
    if (!selectedFile) return

    const btn = document.getElementById('upload-btn')
    btn.disabled    = true
    btn.textContent = '⏳ Processing...'

    // Hide previous report
    document.getElementById('upload-report').style.display  = 'none'
    document.getElementById('upload-error').textContent     = ''
    document.getElementById('upload-success').textContent   = ''

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
        const response = await fetch('http://127.0.0.1:5000/upload-excel', {
            method     : 'POST',
            credentials: 'include',
            body       : formData
        })

        const data = await response.json()

        if (data.success) {
            // Show report
            showUploadReport(data)
            loadTrainingStatus()
            loadRecentRecords()
            loadRecentUploads()
        } else {
            document.getElementById('upload-error').textContent =
                data.message || 'Upload failed. Please try again.'
        }

    } catch (err) {
        document.getElementById('upload-error').textContent =
            'Server error. Please try again.'
    }

    btn.disabled    = false
    btn.textContent = 'Upload and Process'
}

function showUploadReport(data) {
    // Show report section
    document.getElementById('upload-report').style.display = 'block'

    // Fill summary stats
    document.getElementById('stat-total').textContent   = data.total_rows
    document.getElementById('stat-added').textContent   = data.records_added
    document.getElementById('stat-filled').textContent  = data.autofilled_count
    document.getElementById('stat-skipped').textContent = data.skipped_count

    // Autofill details
    if (data.autofill_summary && data.autofill_summary.length > 0) {
        document.getElementById('autofill-details').style.display = 'block'
        let html = ''
        data.autofill_summary.forEach(item => {
            html += `
                <div class="autofill-item">
                    <strong>${item.column}</strong> was missing in 
                    <strong>${item.count}</strong> rows → 
                    filled with default value: <strong>"${item.default}"</strong>
                </div>`
        })
        document.getElementById('autofill-list').innerHTML = html
    } else {
        document.getElementById('autofill-details').style.display = 'none'
    }

    // Skipped rows details
    if (data.skipped_rows && data.skipped_rows.length > 0) {
        document.getElementById('skipped-details').style.display = 'block'
        let html = ''
        data.skipped_rows.forEach(item => {
            html += `
                <div class="skipped-item">
                    <span class="skipped-row-num">Row ${item.row}</span>
                    <span class="skipped-reason">${item.reason}</span>
                </div>`
        })
        if (data.skipped_count > 20) {
            html += `<p class="report-hint">
                     ...and ${data.skipped_count - 20} more rows skipped</p>`
        }
        document.getElementById('skipped-list').innerHTML = html
    } else {
        document.getElementById('skipped-details').style.display = 'none'
    }

    // Retrain status
    document.getElementById('retrain-status-text').textContent =
        data.retrain_status || 'Not triggered'
}

function clearFile() {
    selectedFile = null
    document.getElementById('excel-file').value = ''
    document.getElementById('file-info').style.display = 'none'
    document.getElementById('validation-result').style.display = 'none'
    document.getElementById('upload-btn').disabled = true
    document.getElementById('upload-error').textContent = ''
    document.getElementById('upload-success').textContent = ''
}
// ── Recent Uploads Functions ──

async function loadRecentUploads() {
    try {
        const response = await fetch('http://127.0.0.1:5000/recent-uploads', {
            credentials: 'include'
        })
        const data = await response.json()
        const list = document.getElementById('recent-uploads-list')

        if (!data.uploads || data.uploads.length === 0) {
            list.innerHTML = '<p style="color:#6B7280; font-size:13px;">No uploads yet.</p>'
            return
        }

        list.innerHTML = ''

        data.uploads.forEach(upload => {
            const item = document.createElement('div')
            item.className = 'upload-history-item'

            const hoursText = upload.can_delete
                ? `<span style="color:#D97706">⏱ ${upload.hours_left}h remaining to delete</span>`
                : `<span class="time-expired">🔒 Deletion window expired</span>`

            item.innerHTML = `
                <div class="upload-history-info">
                    <div class="upload-filename">📊 ${upload.filename}</div>
                    <div class="upload-meta">
                        <span>✅ ${upload.records_added} records added</span>
                        <span>👤 ${upload.uploaded_by}</span>
                        <span>🕐 ${upload.uploaded_on}</span>
                    </div>
                </div>
                <div class="upload-actions">
                    <button
                        class="delete-upload-btn"
                        onclick="deleteUpload(${upload.id}, '${upload.filename}')"
                        ${upload.can_delete ? '' : 'disabled'}>
                        ${upload.can_delete ? '🗑️ Delete Upload' : '🔒 Expired'}
                    </button>
                    <div class="${upload.can_delete ? 'time-remaining' : 'time-expired'}">
                        ${hoursText}
                    </div>
                </div>
            `
            list.appendChild(item)
        })

    } catch (err) {
        document.getElementById('recent-uploads-list').innerHTML =
            '<p style="color:#EF4444; font-size:13px;">Error loading uploads.</p>'
    }
}

async function deleteUpload(uploadId, filename) {
    if (!confirm(
        `Are you sure you want to delete "${filename}"?\n\n` +
        `This will also remove all records added from this file.\n` +
        `The model will retrain automatically.`
    )) return

    try {
        const response = await fetch(
            `http://127.0.0.1:5000/delete-upload/${uploadId}`,
            {
                method     : 'DELETE',
                credentials: 'include'
            }
        )
        const data = await response.json()

        if (data.success) {
            alert(`✅ ${data.message}`)
            loadRecentUploads()
            loadTrainingStatus()
            loadRecentRecords()
        } else {
            alert(`❌ ${data.message}`)
        }

    } catch (err) {
        alert('Server error. Please try again.')
    }
}