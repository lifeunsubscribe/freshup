import { useState } from 'react'
import Sheet from '../ui/Sheet'

const QUICK_MINS = [1, 5, 10, 15, 30] as const

interface NewTimerSheetProps {
  open: boolean
  onClose: () => void
  onStart: (name: string, totalSeconds: number) => void
}

export default function NewTimerSheet({ open, onClose, onStart }: NewTimerSheetProps) {
  const [name, setName] = useState('Timer')
  const [minutes, setMinutes] = useState(5)

  function handleStart() {
    if (minutes <= 0) return
    onStart(name.trim() || 'Timer', minutes * 60)
    setName('Timer')
    setMinutes(5)
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="New timer"
      footer={
        <div className="p-4">
          <button
            onClick={handleStart}
            disabled={minutes <= 0}
            className="w-full py-3 bg-olive text-cream rounded-button font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start
          </button>
        </div>
      }
    >
      <div className="px-4 pb-4 space-y-4">
        <div>
          <label
            htmlFor="timer-name"
            className="block text-sm text-text-secondary mb-1"
          >
            Name
          </label>
          <input
            id="timer-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full border border-warm-border rounded-card px-3 py-2 text-sm bg-cream focus:outline-none focus:ring-1 focus:ring-olive"
            placeholder="Timer"
          />
        </div>

        <div>
          <label
            htmlFor="timer-duration"
            className="block text-sm text-text-secondary mb-1"
          >
            Duration (minutes)
          </label>
          <input
            id="timer-duration"
            type="number"
            min={1}
            value={minutes}
            onChange={e => setMinutes(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-full border border-warm-border rounded-card px-3 py-2 text-sm bg-cream focus:outline-none focus:ring-1 focus:ring-olive"
          />
        </div>

        <div>
          <div className="text-sm text-text-secondary mb-2">Quick</div>
          <div className="flex flex-wrap gap-2">
            {QUICK_MINS.map(m => (
              <button
                key={m}
                onClick={() => setMinutes(m)}
                className={`px-3 py-1.5 rounded-pill text-sm font-medium border transition-colors ${
                  minutes === m
                    ? 'bg-olive text-cream border-olive'
                    : 'bg-cream text-text-primary border-warm-border hover:bg-cream-dark'
                }`}
              >
                {m} min
              </button>
            ))}
          </div>
        </div>
      </div>
    </Sheet>
  )
}
