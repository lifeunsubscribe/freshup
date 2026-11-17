import { useState, useEffect, KeyboardEvent, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useUpdateProfile } from '../api/hooks/useAuth'
import { useThemes } from '../api/hooks/useThemes'
import type { TasteLevel } from '../api/types'
import PageContainer from '../components/layout/PageContainer'

// Duplicated from DietarySection — not imported directly to avoid changing that file
const DIETARY_OPTIONS = [
  { value: 'omnivore', label: 'Omnivore' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'pescatarian', label: 'Pescatarian' },
  { value: 'keto', label: 'Keto' },
  { value: 'low_carb', label: 'Low Carb' },
  { value: 'low_sugar', label: 'Low Sugar' },
]

type ThreeState = 'love' | 'never'

function cycleState(current: ThreeState | undefined): ThreeState | undefined {
  if (!current) return 'love'
  if (current === 'love') return 'never'
  return undefined
}

export default function Welcome() {
  const navigate = useNavigate()
  const { currentUser } = useAuth()
  const updateProfile = useUpdateProfile()
  const { data: themes } = useThemes()

  const [step, setStep] = useState(1)
  const [allergies, setAllergies] = useState<string[]>([])
  const [allergyInput, setAllergyInput] = useState('')
  const [selectedDiets, setSelectedDiets] = useState<string[]>([])
  const [cuisineTastes, setCuisineTastes] = useState<Record<string, ThreeState>>({})
  const [ingredientTastes, setIngredientTastes] = useState<Record<string, ThreeState>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  // If already onboarded, go home
  useEffect(() => {
    if (currentUser && currentUser.onboarded_at !== null) {
      navigate('/', { replace: true })
    }
  }, [currentUser, navigate])

  const cuisineValues = useMemo(
    () => themes?.find(t => t.key === 'cuisine')?.values ?? [],
    [themes]
  )

  // Top 24 ingredient values by total content (catalog cards + library count)
  const topIngredientValues = useMemo(() => {
    const values = themes?.find(t => t.key === 'ingredient')?.values ?? []
    return [...values]
      .sort((a, b) => {
        const aCount =
          a.collections.reduce((s, c) => s + c.card_count, 0) + a.library_count
        const bCount =
          b.collections.reduce((s, c) => s + c.card_count, 0) + b.library_count
        return bCount - aCount
      })
      .slice(0, 24)
  }, [themes])

  // --- Step 1: Allergies ---
  const handleAllergyKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addAllergy()
    }
  }

  const addAllergy = () => {
    const trimmed = allergyInput.trim()
    if (trimmed && !allergies.includes(trimmed)) {
      setAllergies(prev => [...prev, trimmed])
      setAllergyInput('')
    }
  }

  // --- Step 3/4: Taste cycling ---
  const cycleCuisine = (value: string) => {
    setCuisineTastes(prev => {
      const next = cycleState(prev[value])
      if (next === undefined) {
        const updated = { ...prev }
        delete updated[value]
        return updated
      }
      return { ...prev, [value]: next }
    })
  }

  const cycleIngredient = (value: string) => {
    setIngredientTastes(prev => {
      const next = cycleState(prev[value])
      if (next === undefined) {
        const updated = { ...prev }
        delete updated[value]
        return updated
      }
      return { ...prev, [value]: next }
    })
  }

  // --- Submission ---
  const handleSkip = async () => {
    setSubmitError(null)
    try {
      await updateProfile.mutateAsync({ onboarded: true })
      navigate('/')
    } catch {
      setSubmitError('Something went wrong. Please try again.')
    }
  }

  const handleFinish = async () => {
    setSubmitError(null)
    const taste_preferences: Record<string, TasteLevel> = {}
    for (const [k, v] of Object.entries(cuisineTastes)) taste_preferences[k] = v
    for (const [k, v] of Object.entries(ingredientTastes)) taste_preferences[k] = v

    try {
      await updateProfile.mutateAsync({
        allergies,
        dietary_profile: selectedDiets,
        taste_preferences,
        onboarded: true,
      })
      navigate('/')
    } catch {
      setSubmitError('Something went wrong. Please try again.')
    }
  }

  const tasteBtnClass = (state: ThreeState | undefined) => {
    if (state === 'love')
      return 'bg-olive text-cream border-olive hover:bg-olive-dark'
    if (state === 'never')
      return 'bg-terra text-cream border-terra hover:bg-terra/80'
    return 'bg-cream-dark text-text-primary border-warm-border hover:bg-mocha/10'
  }

  const tasteLabel = (state: ThreeState | undefined, label: string) => {
    if (state === 'love') return `♥ ${label}`
    if (state === 'never') return `✕ ${label}`
    return label
  }

  return (
    <PageContainer>
      <div className="py-8 max-w-lg mx-auto">
        {/* Header row */}
        <div className="flex items-center justify-between mb-6">
          <p className="text-sm text-text-secondary">Step {step} of 4</p>
          <button
            onClick={handleSkip}
            disabled={updateProfile.isPending}
            className="text-sm text-text-secondary underline hover:text-text-primary disabled:opacity-50"
          >
            Skip for now
          </button>
        </div>

        {/* Step 1: Allergies */}
        {step === 1 && (
          <div data-testid="welcome-step-1">
            <h1 className="text-2xl font-semibold text-text-primary mb-1">
              Any food allergies?
            </h1>
            <p className="text-sm text-text-secondary mb-6">
              We'll keep these out of suggestions.
            </p>

            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={allergyInput}
                onChange={e => setAllergyInput(e.target.value)}
                onKeyDown={handleAllergyKeyDown}
                placeholder="Type an allergy and press Enter"
                className="flex-1 px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
              />
              <button
                onClick={addAllergy}
                disabled={!allergyInput.trim()}
                className="px-4 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add
              </button>
            </div>

            {allergies.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {allergies.map(a => (
                  <div
                    key={a}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-terra/10 text-sm text-terra border border-terra/20"
                  >
                    <span>{a}</span>
                    <button
                      onClick={() =>
                        setAllergies(prev => prev.filter(x => x !== a))
                      }
                      aria-label={`Remove ${a}`}
                      className="hover:bg-terra/20 rounded-full p-0.5 transition-colors"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Diet */}
        {step === 2 && (
          <div data-testid="welcome-step-2">
            <h1 className="text-2xl font-semibold text-text-primary mb-1">
              Any dietary preferences?
            </h1>
            <p className="text-sm text-text-secondary mb-6">
              Select all that apply.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {DIETARY_OPTIONS.map(opt => (
                <label
                  key={opt.value}
                  className="flex items-center gap-3 p-3 rounded-button border border-warm-border hover:bg-cream-dark cursor-pointer transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedDiets.includes(opt.value)}
                    onChange={() =>
                      setSelectedDiets(prev =>
                        prev.includes(opt.value)
                          ? prev.filter(d => d !== opt.value)
                          : [...prev, opt.value]
                      )
                    }
                    className="w-4 h-4 text-olive border-warm-border rounded focus:ring-2 focus:ring-olive focus:ring-offset-2 cursor-pointer"
                  />
                  <span className="text-text-primary font-medium">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Cuisines */}
        {step === 3 && (
          <div data-testid="welcome-step-3">
            <h1 className="text-2xl font-semibold text-text-primary mb-1">
              Favourite cuisines?
            </h1>
            <p className="text-sm text-text-secondary mb-6">
              Tap once for Love, twice for Never suggest, again to clear.
            </p>

            <div className="flex flex-wrap gap-2">
              {cuisineValues.map(v => (
                <button
                  key={v.value}
                  onClick={() => cycleCuisine(v.value)}
                  className={`px-4 py-2 rounded-full border text-sm font-medium transition-colors ${tasteBtnClass(cuisineTastes[v.value])}`}
                >
                  {tasteLabel(cuisineTastes[v.value], v.label)}
                </button>
              ))}
              {cuisineValues.length === 0 && (
                <p className="text-sm text-text-secondary">Loading cuisines…</p>
              )}
            </div>
          </div>
        )}

        {/* Step 4: Ingredients */}
        {step === 4 && (
          <div data-testid="welcome-step-4">
            <h1 className="text-2xl font-semibold text-text-primary mb-1">
              Favourite ingredients?
            </h1>
            <p className="text-sm text-text-secondary mb-6">
              Tap once for Love, twice for Never suggest, again to clear.
            </p>

            <div className="flex flex-wrap gap-2">
              {topIngredientValues.map(v => (
                <button
                  key={v.value}
                  onClick={() => cycleIngredient(v.value)}
                  className={`px-4 py-2 rounded-full border text-sm font-medium transition-colors ${tasteBtnClass(ingredientTastes[v.value])}`}
                >
                  {tasteLabel(ingredientTastes[v.value], v.label)}
                </button>
              ))}
              {topIngredientValues.length === 0 && (
                <p className="text-sm text-text-secondary">Loading ingredients…</p>
              )}
            </div>
          </div>
        )}

        {/* Error message */}
        {submitError && (
          <div className="mt-4 rounded-button border border-terra bg-terra/10 p-3">
            <p className="text-sm text-terra-dark">{submitError}</p>
          </div>
        )}

        {/* Navigation */}
        <div className="flex gap-3 mt-8">
          {step > 1 && (
            <button
              onClick={() => setStep(s => s - 1)}
              className="px-6 py-2 rounded-button bg-cream-dark text-text-primary font-medium hover:bg-mocha/10 transition-colors"
            >
              Back
            </button>
          )}
          {step < 4 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              className="px-6 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={updateProfile.isPending}
              className="px-6 py-2 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {updateProfile.isPending ? 'Saving…' : 'Finish'}
            </button>
          )}
        </div>
      </div>
    </PageContainer>
  )
}
