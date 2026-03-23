import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-cream">
      <header className="mb-12 text-center">
        <h1 className="text-5xl font-bold text-text-primary mb-2">FreshUp</h1>
        <p className="text-lg text-text-secondary">Privacy-First Kitchen Management System</p>
      </header>

      <main className="max-w-2xl mx-auto px-4">
        <div className="bg-cream-dark rounded-card border border-warm-border p-8 shadow-sm">
          <h2 className="text-3xl font-semibold text-text-primary mb-4">Welcome to FreshUp</h2>
          <p className="text-text-secondary mb-6">Your household kitchen management system is ready.</p>

          <div className="mt-8 pt-8 border-t border-warm-border">
            <button
              onClick={() => setCount((count) => count + 1)}
              className="bg-olive hover:bg-olive-dark text-cream font-medium px-6 py-3 rounded-button transition-colors"
            >
              count is {count}
            </button>
            <p className="mt-4 text-text-tertiary">
              Edit <code className="bg-mocha-light text-cream rounded px-2 py-1">src/App.tsx</code> to get started.
            </p>
          </div>
        </div>

        {/* Design Token Demo */}
        <div className="mt-8 bg-cream-dark rounded-card border border-warm-border p-6">
          <h3 className="text-xl font-semibold text-text-primary mb-4">Design System Demo</h3>
          <div className="space-y-4">
            <div className="flex gap-2">
              <div className="bg-olive rounded-button px-4 py-2 text-cream">Olive</div>
              <div className="bg-mocha rounded-button px-4 py-2 text-cream">Mocha</div>
              <div className="bg-terra rounded-button px-4 py-2 text-cream">Terra</div>
            </div>
            <div className="flex gap-2">
              <button className="bg-olive hover:bg-olive-dark text-cream font-medium px-4 py-2 rounded-button transition-colors">
                Button
              </button>
              <span className="bg-olive-light text-cream font-medium px-6 py-2 rounded-pill">
                Pill Shape
              </span>
              <div className="bg-cream border border-warm-border rounded-card px-4 py-2">
                Card Border
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
