import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Link as LinkIcon, ChevronLeft, Info, RotateCcw } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import ImportPreviewCard from '../components/recipe/ImportPreviewCard'
import SavedPageInput from '../components/recipe/SavedPageInput'
import RecipeCard from '../components/recipe/RecipeCard'
import { useImportUrl, useImportHtml, useRecipe, useToggleBookmark } from '../api'
import type { ImportResult } from '../api/types'

// KitchenSanctuary blocks automated fetching — catch this client-side.
function isKitchenSanctuaryUrl(url: string): boolean {
  try {
    return new URL(url).hostname.includes('kitchensanctuary.com')
  } catch {
    return false
  }
}

type Phase =
  | { kind: 'idle' }
  | { kind: 'fetching'; url: string }
  | { kind: 'preview'; recipeId: string; warnings: string[] }
  | { kind: 'duplicate'; recipeId: string; url: string }
  | { kind: 'error'; message: string; url: string }

// ── Preview inner component (needs its own hook calls) ───────────────────────

function PreviewPane({
  recipeId,
  warnings,
  onSave,
  onDiscard,
  isSaving,
}: {
  recipeId: string
  warnings: string[]
  onSave: () => void
  onDiscard: () => void
  isSaving?: boolean
}) {
  const { data: recipe, isLoading } = useRecipe(recipeId)

  if (isLoading || !recipe) {
    return (
      <div className="mx-4 bg-white border border-warm-border rounded-card-lg overflow-hidden animate-pulse">
        <div className="aspect-[4/3] bg-cream-icon" />
        <div className="p-4 space-y-3">
          <div className="h-6 bg-cream-icon rounded-pill w-3/4" />
          <div className="h-4 bg-cream-icon rounded-pill w-1/2" />
        </div>
      </div>
    )
  }

  return (
    <>
      <ImportPreviewCard recipe={recipe} warnings={warnings} />
      <div className="h-4" />
      {/* Sticky action bar */}
      <div className="mt-auto px-4 py-3 bg-cream border-t border-warm-border flex gap-2">
        <button
          onClick={onDiscard}
          className="h-12 px-4 rounded-button bg-white border border-warm-btn-border text-text-primary text-[15px] inline-flex items-center justify-center"
        >
          Not this one
        </button>
        <button
          onClick={onSave}
          disabled={isSaving}
          className="h-12 flex-1 px-4 rounded-button bg-olive text-white text-[15px] font-medium inline-flex items-center justify-center disabled:opacity-60 transition-opacity"
        >
          {isSaving ? 'Saving…' : 'Save to library'}
        </button>
      </div>
    </>
  )
}

// ── Duplicate inner component ────────────────────────────────────────────────

function DuplicatePane({
  recipeId,
  onAddDifferent,
}: {
  recipeId: string
  onAddDifferent: () => void
}) {
  const navigate = useNavigate()
  const { data: recipe, isLoading } = useRecipe(recipeId)

  return (
    <div className="mx-4 mt-4 p-4 bg-white border border-warm-border rounded-card-lg">
      <h2 className="text-[15px] font-medium text-text-primary">
        Already in the library<span className="text-olive">.</span>
      </h2>
      <p className="text-[13px] leading-normal text-text-secondary mt-1">
        Nothing new was added. Here it is.
      </p>
      {!isLoading && recipe && (
        <div className="w-[190px] mx-auto mt-4">
          <RecipeCard
            recipe={{
              id: recipe.id,
              name: recipe.name,
              source_type: recipe.source_type,
              cook_time_minutes: recipe.cook_time_minutes,
              prep_time_minutes: recipe.prep_time_minutes,
              tags: recipe.tags,
            }}
            variant="grid"
          />
        </div>
      )}
      <button
        onClick={() => navigate(`/recipes/${recipeId}`)}
        className="h-12 w-full mt-4 px-4 rounded-button bg-olive text-white text-[15px] font-medium inline-flex items-center justify-center"
      >
        Open recipe
      </button>
      <button
        onClick={onAddDifferent}
        className="h-12 w-full mt-2 px-4 rounded-button bg-white border border-warm-btn-border text-text-primary text-[15px] inline-flex items-center justify-center"
      >
        Add a different recipe
      </button>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function AddRecipe() {
  const navigate = useNavigate()
  const [linkUrl, setLinkUrl] = useState('')
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })

  const importUrl = useImportUrl()
  const importHtml = useImportHtml()
  const bookmarkMutation = useToggleBookmark()

  const isKS = isKitchenSanctuaryUrl(linkUrl)
  const isFetchDisabled = linkUrl.trim().length === 0

  // ── Shared result handler ────────────────────────────────────────────────

  function handleImportResult(result: ImportResult, url: string) {
    if (result.status === 'success' && result.recipe_id) {
      setPhase({ kind: 'preview', recipeId: result.recipe_id, warnings: result.warnings ?? [] })
    } else if (result.status === 'duplicate' && result.recipe_id) {
      setPhase({ kind: 'duplicate', recipeId: result.recipe_id, url })
    } else {
      setPhase({ kind: 'error', message: result.message ?? 'The import did not complete.', url })
    }
  }

  function handleImportError(error: unknown, url: string) {
    const msg =
      error instanceof Error ? error.message : 'Something went wrong. Please try again.'
    setPhase({ kind: 'error', message: msg, url })
  }

  // ── Link submit ──────────────────────────────────────────────────────────

  function submitLink(url: string) {
    setPhase({ kind: 'fetching', url })
    importUrl.mutate(
      { url },
      {
        onSuccess: (result) => handleImportResult(result, url),
        onError: (error) => handleImportError(error, url),
      }
    )
  }

  function handleLinkSubmit(e: React.FormEvent) {
    e.preventDefault()
    submitLink(linkUrl)
  }

  // ── Saved page submit ────────────────────────────────────────────────────

  function handleSavedPaste(html: string, sourceUrl: string) {
    setPhase({ kind: 'fetching', url: sourceUrl })
    importHtml.mutate(
      { html, source_url: sourceUrl },
      {
        onSuccess: (result) => handleImportResult(result, sourceUrl),
        onError: (error) => handleImportError(error, sourceUrl),
      }
    )
  }

  function handleSavedFile(file: File, sourceUrl: string) {
    setPhase({ kind: 'fetching', url: sourceUrl })
    importHtml.mutate(
      { file, source_url: sourceUrl },
      {
        onSuccess: (result) => handleImportResult(result, sourceUrl),
        onError: (error) => handleImportError(error, sourceUrl),
      }
    )
  }

  // ── Save (bookmark) ──────────────────────────────────────────────────────

  function handleSave() {
    if (phase.kind !== 'preview') return
    bookmarkMutation.mutate(
      { recipeId: phase.recipeId, next: true },
      { onSuccess: () => navigate(`/recipes/${phase.recipeId}`) }
    )
  }

  function resetToIdle() {
    setPhase({ kind: 'idle' })
    importUrl.reset()
    importHtml.reset()
  }

  // ── Sent URL strip ───────────────────────────────────────────────────────

  const sentUrl =
    phase.kind === 'fetching' || phase.kind === 'duplicate' || phase.kind === 'error'
      ? phase.url
      : null

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <PageContainer>
      <div className="py-0 space-y-0">
        {/* Header */}
        <header className="px-0 pt-3 pb-3">
          <Link
            to="/recipes"
            className="inline-flex items-center gap-1 h-11 -ml-1.5 pr-3 text-olive text-[14px]"
          >
            <ChevronLeft size={20} />
            Recipes
          </Link>
          <h1 className="text-[22px] font-medium leading-[1.3] text-text-primary">
            Add a recipe<span className="text-olive">.</span>
          </h1>
        </header>

        {/* Sent URL strip (fetching / duplicate / error states) */}
        {sentUrl && (
          <div className="mx-4 px-3 py-3 bg-white border border-warm-border rounded-card flex items-center gap-2 text-[13px] mb-3">
            <LinkIcon size={16} className="text-text-tertiary shrink-0" />
            <span className="flex-1 truncate text-text-secondary">{sentUrl}</span>
            <button onClick={resetToIdle} className="text-olive text-[13px]">
              Edit
            </button>
          </div>
        )}

        {/* Fetching state: skeleton card */}
        {phase.kind === 'fetching' && (
          <>
            <div
              className="mx-4 mt-4 bg-white border border-warm-border rounded-card-lg overflow-hidden"
              role="status"
              aria-label="Fetching recipe"
            >
              <div className="aspect-[4/3] bg-cream-icon animate-pulse" />
              <div className="p-4">
                <h2 className="text-[22px] font-medium leading-[1.3] text-text-primary">
                  {(() => {
                    try { return new URL(phase.url).hostname.replace(/^www\./, '') } catch { return '' }
                  })()}
                </h2>
                <div className="grid grid-cols-3 gap-2 mt-4">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-[58px] rounded-card bg-cream-icon animate-pulse" />
                  ))}
                </div>
                <div className="flex items-center gap-2 mt-5 text-[13px] text-text-secondary">
                  <span className="inline-block w-4 h-4 rounded-full border-2 border-warm border-t-olive animate-spin" />
                  Reading the ingredients…
                </div>
              </div>
            </div>
            <button onClick={resetToIdle} className="mx-4 h-11 mt-1 text-[14px] text-text-secondary">
              Cancel
            </button>
          </>
        )}

        {/* Preview state */}
        {phase.kind === 'preview' && (
          <PreviewPane
            recipeId={phase.recipeId}
            warnings={phase.warnings}
            onSave={handleSave}
            onDiscard={resetToIdle}
            isSaving={bookmarkMutation.isPending}
          />
        )}

        {/* Duplicate state */}
        {phase.kind === 'duplicate' && (
          <DuplicatePane recipeId={phase.recipeId} onAddDifferent={resetToIdle} />
        )}

        {/* Error state */}
        {phase.kind === 'error' && (
          <>
            <div className="mx-4 mt-4 p-4 bg-mocha-light border border-mocha-border rounded-card-lg">
              <div className="flex gap-2">
                <Info size={20} className="text-mocha mt-0.5 shrink-0" />
                <div>
                  <h2 className="text-[15px] font-medium text-text-primary">
                    Could not import<span className="text-olive">.</span>
                  </h2>
                  <p className="text-[13px] leading-normal text-mocha-dark mt-1">
                    {phase.message}
                  </p>
                </div>
              </div>
              <button
                onClick={() => submitLink(phase.url)}
                className="h-12 w-full mt-3 px-4 rounded-button bg-olive text-white text-[15px] font-medium inline-flex items-center justify-center gap-2"
              >
                <RotateCcw size={16} />
                Try again
              </button>
            </div>

            {/* Or skip the wait — simplified saved-page prompt */}
            <div className="mx-4 mt-4 p-4 bg-white border border-warm-border rounded-card-lg">
              <h2 className="text-[15px] font-medium text-text-primary">
                Or skip the wait<span className="text-olive">.</span>
              </h2>
              <p className="text-[13px] leading-normal text-text-secondary mt-1">
                Open the recipe in your browser, save or copy the page, and hand it over here.
              </p>
              <div className="mt-3">
                <SavedPageInput
                  onSubmitPaste={handleSavedPaste}
                  onSubmitFile={handleSavedFile}
                  disabled={importHtml.isPending}
                />
              </div>
            </div>
          </>
        )}

        {/* Idle state: link input + saved page section */}
        {phase.kind === 'idle' && (
          <>
            {/* Link input card */}
            <form
              onSubmit={handleLinkSubmit}
              className="mx-4 p-4 bg-white border border-warm-border rounded-card-lg"
            >
              <label htmlFor="recipe-url" className="block text-[14px] font-medium mb-2">
                Paste a link
              </label>
              <div className="flex gap-2">
                <div className="flex-1 min-w-0">
                  <div className="h-12 flex items-center gap-2 px-3 rounded-input border border-warm-border bg-white">
                    <LinkIcon size={18} className="text-text-tertiary shrink-0" />
                    <input
                      id="recipe-url"
                      type="url"
                      value={linkUrl}
                      onChange={(e) => setLinkUrl(e.target.value)}
                      placeholder="Paste a recipe link…"
                      className="flex-1 text-[14px] bg-transparent placeholder:text-text-tertiary focus:outline-none"
                    />
                  </div>
                </div>
                {linkUrl.trim().length === 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.readText().then((text) => setLinkUrl(text)).catch(() => {})
                    }}
                    className="h-12 px-3 rounded-button bg-white border border-warm-btn-border text-text-primary text-[14px] inline-flex items-center justify-center"
                  >
                    Paste
                  </button>
                )}
              </div>
              <p className="text-[12px] leading-[1.4] text-text-secondary mt-2">
                Works for HelloFresh and most recipe sites.
              </p>

              {/* KitchenSanctuary intercept */}
              {isKS ? (
                <div className="mt-3 p-3 rounded-card bg-mocha-light border border-mocha-border">
                  <p className="text-[14px] font-medium text-text-primary">
                    This one needs the saved page<span className="text-olive">.</span>
                  </p>
                  <p className="text-[13px] leading-normal text-mocha-dark mt-1">
                    Kitchen Sanctuary only opens its door to people, not apps, so open the
                    recipe in your own browser, save or copy the page, and hand it over here.
                  </p>
                  <div className="mt-3 space-y-2">
                    <button
                      type="button"
                      onClick={() => {
                        const el = document.getElementById('saved-page-section')
                        el?.scrollIntoView({ behavior: 'smooth' })
                      }}
                      className="h-12 w-full px-4 rounded-button bg-olive text-white text-[15px] font-medium inline-flex items-center justify-center"
                    >
                      Show me how
                    </button>
                    <button
                      type="button"
                      onClick={() => submitLink(linkUrl)}
                      className="w-full h-11 text-[14px] text-text-secondary"
                    >
                      Try the link anyway
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="submit"
                  disabled={isFetchDisabled}
                  className="h-12 w-full mt-4 px-4 rounded-button bg-olive text-white text-[15px] font-medium inline-flex items-center justify-center disabled:bg-warm-divider disabled:text-text-tertiary transition-colors"
                >
                  Fetch recipe
                </button>
              )}
            </form>

            {/* Which sources work? */}
            <a
              href="#"
              className="mx-4 inline-flex items-center gap-1.5 min-h-[44px] text-[13px] text-olive"
            >
              <Info size={16} />
              Which sources work?
            </a>

            {/* Saved-page section */}
            <div id="saved-page-section">
              <SavedPageInput
                className="mx-4"
                onSubmitPaste={handleSavedPaste}
                onSubmitFile={handleSavedFile}
              />
            </div>
          </>
        )}
      </div>
    </PageContainer>
  )
}
