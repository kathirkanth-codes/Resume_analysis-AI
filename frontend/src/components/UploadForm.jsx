import { useState, useRef } from 'react'

export default function UploadForm({ file, setFile, jobDescription, setJobDescription, onSubmit }) {
  const [validationMsg, setValidationMsg] = useState('')
  const inputRef = useRef(null)

  function handleFileChange(e) {
    const selected = e.target.files[0]
    if (selected) {
      setFile(selected)
      setValidationMsg('')
    }
  }

  function handleSubmit() {
    if (!file) {
      setValidationMsg('⚠ ERROR: NO FILE SELECTED. PLEASE UPLOAD A PDF RESUME FIRST.')
      return
    }
    setValidationMsg('')
    onSubmit()
  }

  return (
    <div className="retro-card">
      <div className="retro-card-header">📁 UPLOAD RESUME — STEP 1 OF 1</div>
      <div className="retro-card-body">
        <div className="upload-zone" onClick={() => inputRef.current.click()}>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <div style={{ fontSize: '36px', marginBottom: '8px' }}>📄</div>
          <div>CLICK TO UPLOAD YOUR RESUME (.PDF)</div>
          {file && (
            <div style={{ marginTop: '10px', color: '#00AA00', fontSize: '16px', fontFamily: '"VT323", monospace', letterSpacing: '1px' }}>
              ✔ FILE LOADED: {file.name}
            </div>
          )}
        </div>

        {validationMsg && <div className="retro-alert">{validationMsg}</div>}

        <div style={{ marginBottom: '16px' }}>
          <label className="retro-label">PASTE JOB DESCRIPTION (OPTIONAL)</label>
          <textarea
            className="retro-textarea"
            value={jobDescription}
            onChange={e => setJobDescription(e.target.value)}
            placeholder="Paste the job description here to get a targeted analysis..."
            rows={4}
          />
        </div>

        <button className="retro-btn" onClick={handleSubmit}>
          ▶ ANALYZE MY RESUME
        </button>
      </div>
    </div>
  )
}
