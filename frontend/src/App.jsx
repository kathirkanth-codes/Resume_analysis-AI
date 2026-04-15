import { useState } from 'react'
import Header from './components/Header.jsx'
import UploadForm from './components/UploadForm.jsx'
import ScorePanel from './components/ScorePanel.jsx'
import WeakBullets from './components/WeakBullets.jsx'
import MissingSkills from './components/MissingSkills.jsx'
import RoastPanel from './components/RoastPanel.jsx'
import LoadingScreen from './components/LoadingScreen.jsx'
import ErrorBanner from './components/ErrorBanner.jsx'
import { analyzeResume } from './api/analyzeResume.js'

export default function App() {
  const [file, setFile] = useState(null)
  const [jobDescription, setJobDescription] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await analyzeResume(file, jobDescription)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-container">
      <Header />
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      {loading && <LoadingScreen />}
      {!loading && (
        <>
          <UploadForm
            file={file}
            setFile={setFile}
            jobDescription={jobDescription}
            setJobDescription={setJobDescription}
            onSubmit={handleSubmit}
          />
          {result && (
            <>
              <ScorePanel evaluation={result.evaluation} />
              <WeakBullets weakPoints={result.evaluation.weak_points} />
              <MissingSkills missingSkills={result.evaluation.missing_skills} />
              <RoastPanel roast={result.roast} />
            </>
          )}
        </>
      )}
      <div className="construction-banner">
        <span className="construction-text">
          🚧 SITE UNDER CONSTRUCTION — POWERED BY AI ORACLE v1.0 🚧
        </span>
      </div>
    </div>
  )
}
