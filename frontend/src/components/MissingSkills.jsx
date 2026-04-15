export default function MissingSkills({ missingSkills }) {
  return (
    <div className="retro-card">
      <div className="retro-card-header">🔍 MISSING SKILLS GAP</div>
      <div className="retro-card-body">
        {missingSkills.length === 0 ? (
          <div style={{ color: '#00FF00', fontFamily: '"VT323", monospace', fontSize: '20px', letterSpacing: '1px' }}>
            ✔ No missing skills detected — full coverage!
          </div>
        ) : (
          <>
            <div style={{ fontFamily: '"Share Tech Mono", monospace', fontSize: '14px', color: '#bbbbbb', marginBottom: '14px' }}>
              The following skills were not found in your resume:
            </div>
            <div className="skills-grid">
              {missingSkills.map((skill, i) => (
                <span key={i} className="skill-badge">{skill}</span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
