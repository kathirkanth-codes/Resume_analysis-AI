import { useState, useEffect } from 'react'

const MESSAGES = [
  'PARSING RESUME...',
  'CONSULTING THE AI ORACLE...',
  'GENERATING ROAST...',
]

const ASCII_FRAMES = [
  '[░░░░░░░░░░░░░░░░░░░░]',
  '[██░░░░░░░░░░░░░░░░░░]',
  '[████░░░░░░░░░░░░░░░░]',
  '[██████░░░░░░░░░░░░░░]',
  '[████████░░░░░░░░░░░░]',
  '[██████████░░░░░░░░░░]',
  '[████████████░░░░░░░░]',
  '[██████████████░░░░░░]',
  '[████████████████░░░░]',
  '[██████████████████░░]',
  '[████████████████████]',
]

export default function LoadingScreen() {
  const [msgIndex, setMsgIndex] = useState(0)
  const [frameIndex, setFrameIndex] = useState(0)

  useEffect(() => {
    const msgTimer = setInterval(() => {
      setMsgIndex(prev => (prev + 1) % MESSAGES.length)
    }, 1800)
    return () => clearInterval(msgTimer)
  }, [])

  useEffect(() => {
    const frameTimer = setInterval(() => {
      setFrameIndex(prev => (prev + 1) % ASCII_FRAMES.length)
    }, 200)
    return () => clearInterval(frameTimer)
  }, [])

  return (
    <div className="loading-overlay">
      <div style={{
        fontFamily: '"VT323", "Courier New", monospace',
        color: '#00FF00', fontSize: '36px',
        textTransform: 'uppercase', letterSpacing: '4px',
        textShadow: '0 0 16px #00FF00, 0 0 32px rgba(0,255,0,0.4)', marginBottom: '24px',
      }}>
        ★ AI RESUME ANALYZER ★
      </div>

      <div style={{
        fontFamily: '"VT323", "Courier New", monospace',
        color: '#FFD700', fontSize: '22px',
        letterSpacing: '3px', marginBottom: '20px', minHeight: '28px',
      }}>
        {MESSAGES[msgIndex]}
      </div>

      <div className="loading-bar-outer">
        <div className="loading-bar-fill" />
      </div>

      <div style={{
        fontFamily: '"VT323", "Courier New", monospace',
        color: '#00FF00', fontSize: '20px', marginTop: '14px', letterSpacing: '2px',
      }}>
        {ASCII_FRAMES[frameIndex]} PROCESSING...
      </div>

      <div style={{
        fontFamily: '"Share Tech Mono", "Courier New", monospace',
        color: '#666', fontSize: '13px', marginTop: '26px',
        letterSpacing: '1px',
      }}>
        DO NOT CLOSE THIS WINDOW
      </div>
    </div>
  )
}
