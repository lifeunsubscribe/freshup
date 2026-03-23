import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="app">
      <header className="app-header">
        <h1>FreshUp</h1>
        <p>Privacy-First Kitchen Management System</p>
      </header>

      <main className="app-main">
        <div className="welcome-card">
          <h2>Welcome to FreshUp</h2>
          <p>Your household kitchen management system is ready.</p>

          <div className="counter-demo">
            <button onClick={() => setCount((count) => count + 1)}>
              count is {count}
            </button>
            <p>
              Edit <code>src/App.tsx</code> to get started.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
