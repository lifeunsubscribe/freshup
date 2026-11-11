import { useState, useRef } from 'react'
import { Paperclip, Upload } from 'lucide-react'

export interface SavedPageInputProps {
  onSubmitPaste: (html: string, sourceUrl: string) => void
  onSubmitFile: (file: File, sourceUrl: string) => void
  disabled?: boolean
  /** Extra classes on the root element (e.g. "mx-4" when used at page level). */
  className?: string
}

type Mode = 'paste' | 'file'

/**
 * Let the user hand over a saved page either by pasting its HTML or uploading
 * the file. Used for sites (Kitchen Sanctuary) that refuse automated fetching.
 *
 * Both paths require a source URL so the importer knows which parser to use.
 */
export default function SavedPageInput({ onSubmitPaste, onSubmitFile, disabled, className = '' }: SavedPageInputProps) {
  const [mode, setMode] = useState<Mode>('paste')
  const [html, setHtml] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const canSubmitPaste = mode === 'paste' && html.trim().length > 0 && sourceUrl.trim().length > 0
  const canSubmitFile = mode === 'file' && file !== null && sourceUrl.trim().length > 0

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (mode === 'paste' && canSubmitPaste) {
      onSubmitPaste(html, sourceUrl)
    } else if (mode === 'file' && canSubmitFile && file) {
      onSubmitFile(file, sourceUrl)
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null
    setFile(picked)
  }

  return (
    <div className={`p-4 bg-white border border-warm-border rounded-card-lg ${className}`.trim()}>
      <p className="text-[14px] font-medium">Or hand over the saved page</p>
      <p className="text-[12px] leading-[1.4] text-text-secondary mt-1">
        For sites that turn links away, like Kitchen Sanctuary.
      </p>

      {/* Mode selector */}
      <div className="grid grid-cols-2 gap-2 mt-3">
        <button
          type="button"
          onClick={() => setMode('paste')}
          className={`h-11 px-3 rounded-button-sm border text-[14px] inline-flex items-center justify-center gap-2 transition-colors ${
            mode === 'paste'
              ? 'bg-olive text-white border-olive'
              : 'bg-white border-warm-btn-border text-text-primary'
          }`}
        >
          <Paperclip size={18} />
          Paste page
        </button>
        <button
          type="button"
          onClick={() => {
            setMode('file')
            setTimeout(() => fileRef.current?.click(), 0)
          }}
          className={`h-11 px-3 rounded-button-sm border text-[14px] inline-flex items-center justify-center gap-2 transition-colors ${
            mode === 'file'
              ? 'bg-olive text-white border-olive'
              : 'bg-white border-warm-btn-border text-text-primary'
          }`}
        >
          <Upload size={18} />
          Upload
        </button>
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        {/* Source URL — required for both modes */}
        <div>
          <label htmlFor="saved-page-source-url" className="block text-[12px] uppercase tracking-[0.06em] text-text-tertiary mb-1.5">
            Source URL
          </label>
          <input
            id="saved-page-source-url"
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://www.kitchensanctuary.com/recipe-name"
            className="w-full h-12 px-3 rounded-input border border-warm-border text-[14px] bg-white placeholder:text-text-tertiary focus:outline-none focus:border-olive"
            disabled={disabled}
            required
          />
        </div>

        {mode === 'paste' ? (
          <div>
            <label htmlFor="saved-page-html" className="block text-[12px] uppercase tracking-[0.06em] text-text-tertiary mb-1.5">
              Paste the page HTML
            </label>
            <textarea
              id="saved-page-html"
              value={html}
              onChange={(e) => setHtml(e.target.value)}
              placeholder="Paste the full page source here…"
              rows={5}
              className="w-full px-3 py-2.5 rounded-input border border-warm-border text-[14px] bg-white placeholder:text-text-tertiary focus:outline-none focus:border-olive resize-none"
              disabled={disabled}
            />
          </div>
        ) : (
          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".html,.htm,.txt"
              onChange={handleFileChange}
              className="sr-only"
              aria-label="Upload saved page file"
            />
            {file ? (
              <div className="flex items-center gap-3 p-3 rounded-card bg-cream border border-warm-border">
                <div className="w-10 h-10 rounded-button-sm bg-cream-icon text-olive flex items-center justify-center shrink-0">
                  <Paperclip size={20} />
                </div>
                <span className="flex-1 min-w-0">
                  <span className="block text-[14px] truncate">{file.name}</span>
                  <span className="block text-[12px] text-text-secondary">
                    {Math.round(file.size / 1024)} KB
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }}
                  className="w-11 h-11 flex items-center justify-center text-text-secondary"
                  aria-label="Remove file"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="w-full h-11 rounded-button-sm border border-warm-btn-border text-[14px] text-text-secondary inline-flex items-center justify-center gap-2"
              >
                <Upload size={18} />
                Choose file (.html, .htm, .txt)
              </button>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={disabled || (mode === 'paste' ? !canSubmitPaste : !canSubmitFile)}
          className="h-12 w-full px-4 rounded-button bg-olive text-white text-[15px] font-medium inline-flex items-center justify-center disabled:bg-warm-divider disabled:text-text-tertiary transition-colors"
        >
          Read recipe
        </button>
      </form>
    </div>
  )
}
