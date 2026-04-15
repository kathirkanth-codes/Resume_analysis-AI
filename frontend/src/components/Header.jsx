export default function Header() {
  return (
    <div className="retro-card" style={{ textAlign: 'center' }}>
      <div style={{ padding: '28px 20px 18px' }}>
        <h1 className="header-title">
          ★ AI RESUME ANALYZER v1.0 ★
        </h1>

        <div style={{ overflow: 'hidden', whiteSpace: 'nowrap', marginBottom: '16px' }}>
          <span style={{
            display: 'inline-block',
            animation: 'marquee 14s linear infinite',
            fontFamily: '"VT323", "Courier New", monospace',
            color: '#FF69B4',
            fontSize: '20px',
            letterSpacing: '2px',
          }}>
            &nbsp;&nbsp;&nbsp;Upload your resume. Get brutally honest feedback. Improve your chances.
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Upload your resume. Get brutally honest feedback. Improve your chances.&nbsp;&nbsp;&nbsp;
          </span>
        </div>

        <hr className="retro-divider" />

        <p style={{
          fontFamily: '"Share Tech Mono", "Courier New", monospace',
          fontSize: '13px',
          color: '#777',
          marginTop: '12px',
          letterSpacing: '1px',
        }}>
          [ BEST VIEWED IN NETSCAPE NAVIGATOR 4.0 AT 800x600 ]
        </p>
      </div>
    </div>
  )
}
