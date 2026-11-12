import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AddRecipe from './AddRecipe'
import { renderWithProviders } from '../test/renderWithProviders'

// ── Mock the whole API surface touched by this page ──────────────────────────

const mockImportUrlMutate = vi.fn()
const mockImportHtmlMutate = vi.fn()
const mockBookmarkMutate = vi.fn()

vi.mock('../api', () => ({
  useImportUrl: vi.fn(),
  useImportHtml: vi.fn(),
  useRecipe: vi.fn(),
  useToggleBookmark: vi.fn(),
}))

// RecipeCard (shown in duplicate state) reads engagement from this hook.
vi.mock('../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelations: () => ({ data: new Map() }),
  useToggleBookmark: () => ({ mutate: vi.fn(), isPending: false }),
  useToggleLike: () => ({ mutate: vi.fn() }),
}))

// Source health — default: all healthy so the alert never shows in unrelated tests.
vi.mock('../api/hooks/useSourceHealth', () => ({
  useSourceHealth: vi.fn(() => ({ data: [], isLoading: false, isError: false })),
  failingSources: vi.fn((s: Array<{ status: string }>) => s.filter(x => x.status === 'failing')),
}))

// Auth context — default: member so coordinator links never appear in unrelated tests.
vi.mock('../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    currentUser: { id: '1', name: 'Alex', email: 'alex@example.com', role: 'member' },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    switchUser: vi.fn(),
  })),
}))

import { useImportUrl, useImportHtml, useRecipe, useToggleBookmark } from '../api'
import { useSourceHealth } from '../api/hooks/useSourceHealth'
import { useAuth } from '../contexts/AuthContext'

// ── Helpers ──────────────────────────────────────────────────────────────────

const mockRecipe = {
  id: 'recipe-123',
  name: 'Sweet chili tofu bowls',
  source_type: 'hellofresh_card',
  source_url: 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls',
  source_image: null,
  steps: [],
  created_by: null,
  notes: null,
  tags: ['vegan', 'asian-inspired'],
  cook_time_minutes: 25,
  prep_time_minutes: 10,
  base_servings: 2,
  times_cooked: 0,
  is_persisted: false,
  variation_groups: null,
  nutritional_info: null,
  ingredients: [
    { id: 'i1', recipe_id: 'recipe-123', ingredient_name: 'Firm tofu', quantity: 14, unit: 'oz', variation_group: null, variation_diet: null, is_optional: false, step_index: null },
    { id: 'i2', recipe_id: 'recipe-123', ingredient_name: 'Salt', quantity: 0.001, unit: '', variation_group: null, variation_diet: null, is_optional: false, step_index: null },
  ],
}

function setupMocks({
  importStatus = 'idle',
  importResult = null as { status: string; recipe_id?: string; warnings?: string[]; message?: string } | null,
  recipeData = mockRecipe,
}: {
  importStatus?: 'idle' | 'pending' | 'success' | 'error'
  importResult?: { status: string; recipe_id?: string; warnings?: string[]; message?: string } | null
  recipeData?: typeof mockRecipe
} = {}) {
  vi.mocked(useImportUrl).mockReturnValue({
    mutate: mockImportUrlMutate,
    isPending: importStatus === 'pending',
    isSuccess: importStatus === 'success',
    isError: importStatus === 'error',
    reset: vi.fn(),
    data: importResult ?? undefined,
  } as any)

  vi.mocked(useImportHtml).mockReturnValue({
    mutate: mockImportHtmlMutate,
    isPending: importStatus === 'pending',
    isSuccess: importStatus === 'success',
    isError: importStatus === 'error',
    reset: vi.fn(),
    data: importResult ?? undefined,
  } as any)

  vi.mocked(useRecipe).mockReturnValue({
    data: recipeData,
    isLoading: false,
    isError: false,
    error: null,
  } as any)

  vi.mocked(useToggleBookmark).mockReturnValue({
    mutate: mockBookmarkMutate,
    isPending: false,
  } as any)
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('AddRecipe page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMocks()
  })

  describe('route and structure', () => {
    it('renders behind /recipes/add and shows the page heading', () => {
      renderWithProviders(<AddRecipe />, { route: '/recipes/add' })
      expect(screen.getByRole('heading', { name: /add a recipe/i })).toBeInTheDocument()
    })

    it('shows a back link to /recipes', () => {
      renderWithProviders(<AddRecipe />)
      const backLink = screen.getByRole('link', { name: /recipes/i })
      expect(backLink).toHaveAttribute('href', '/recipes')
    })

    it('renders the link input in idle state', () => {
      renderWithProviders(<AddRecipe />)
      expect(screen.getByLabelText(/paste a link/i)).toBeInTheDocument()
    })

    it('renders the saved-page section in idle state', () => {
      renderWithProviders(<AddRecipe />)
      expect(screen.getByText(/or hand over the saved page/i)).toBeInTheDocument()
    })
  })

  describe('link submit → success → preview', () => {
    it('shows the preview after a successful import', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      // Simulate user typing a URL
      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls')

      // Grab the mutate mock and trigger success
      const fetchBtn = screen.getByRole('button', { name: /fetch recipe/i })
      await user.click(fetchBtn)

      // The mutate call should have fired
      expect(mockImportUrlMutate).toHaveBeenCalledWith(
        { url: 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls' },
        expect.any(Object)
      )

      // Simulate the onSuccess callback with a success result
      const onSuccessCall = mockImportUrlMutate.mock.calls[0][1]
      onSuccessCall.onSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: ['Salt'] })

      await waitFor(() => {
        // Recipe name shown in preview
        expect(screen.getByText('Sweet chili tofu bowls')).toBeInTheDocument()
      })
    })

    it('preview shows ingredient list from the fetched recipe', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: [] })

      await waitFor(() => {
        expect(screen.getByText('Firm tofu')).toBeInTheDocument()
      })
    })

    it('preview shows the no-amount note when warnings are present', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: ['Salt'] })

      await waitFor(() => {
        expect(screen.getByText(/No amount given for: Salt/i)).toBeInTheDocument()
      })
    })

    it('preview shows prep time, cook time, and servings tiles', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: [] })

      await waitFor(() => {
        expect(screen.getByText('10 min')).toBeInTheDocument() // prep
        expect(screen.getByText('25 min')).toBeInTheDocument() // cook
        expect(screen.getByText('2')).toBeInTheDocument()      // servings
      })
    })

    it('preview shows tags', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: [] })

      await waitFor(() => {
        expect(screen.getByText('vegan')).toBeInTheDocument()
        expect(screen.getByText('asian-inspired')).toBeInTheDocument()
      })
    })
  })

  describe('duplicate response', () => {
    it('shows the existing recipe card for a duplicate', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'duplicate', recipe_id: 'recipe-123' })

      await waitFor(() => {
        expect(screen.getByText(/already in the library/i)).toBeInTheDocument()
      })
    })

    it('duplicate state renders a RecipeCard linking to the existing recipe', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'duplicate', recipe_id: 'recipe-123' })

      await waitFor(() => {
        expect(screen.getByText('Sweet chili tofu bowls')).toBeInTheDocument()
      })

      const openBtn = screen.getByRole('button', { name: /open recipe/i })
      expect(openBtn).toBeInTheDocument()
    })

    it('duplicate state uses no alert colour (mocha)', async () => {
      const user = userEvent.setup()
      const { container } = renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'duplicate', recipe_id: 'recipe-123' })

      await waitFor(() =>
        expect(screen.getByText(/already in the library/i)).toBeInTheDocument()
      )

      // The duplicate container should not have mocha-light background
      expect(container.querySelector('.bg-mocha-light')).not.toBeInTheDocument()
    })
  })

  describe('error response', () => {
    it('shows the error message in the mocha variant', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'error', message: 'The page took longer than 30 seconds.' })

      await waitFor(() => {
        expect(screen.getByText(/the page took longer than 30 seconds/i)).toBeInTheDocument()
      })
    })

    it('error state shows retry button', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'error', message: 'Failed.' })

      await waitFor(() =>
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
      )
    })

    it('error state offers the saved-page path', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'error', message: 'Failed.' })

      await waitFor(() =>
        expect(screen.getByText(/or skip the wait/i)).toBeInTheDocument()
      )
    })

    it('error state uses mocha background (attention, not terracotta)', async () => {
      const user = userEvent.setup()
      const { container } = renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]
      onSuccess({ status: 'error', message: 'Failed.' })

      await waitFor(() =>
        expect(screen.getByText(/could not import/i)).toBeInTheDocument()
      )

      expect(container.querySelector('.bg-mocha-light')).toBeInTheDocument()
      expect(container.querySelector('.bg-terra-light')).not.toBeInTheDocument()
    })
  })

  describe('Kitchen Sanctuary intercept', () => {
    it('shows the KS intercept banner when a kitchensanctuary.com URL is typed', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.kitchensanctuary.com/crispy-sesame-chicken/')

      await waitFor(() => {
        expect(screen.getByText(/this one needs the saved page/i)).toBeInTheDocument()
      })
    })

    it('intercept is shown without making any network request', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.kitchensanctuary.com/recipe/')

      await waitFor(() =>
        expect(screen.getByText(/this one needs the saved page/i)).toBeInTheDocument()
      )

      expect(mockImportUrlMutate).not.toHaveBeenCalled()
    })

    it('"Try the link anyway" sends the KS URL to import-url', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.kitchensanctuary.com/recipe/')

      await waitFor(() =>
        expect(screen.getByText(/try the link anyway/i)).toBeInTheDocument()
      )

      await user.click(screen.getByRole('button', { name: /try the link anyway/i }))

      expect(mockImportUrlMutate).toHaveBeenCalledWith(
        { url: 'https://www.kitchensanctuary.com/recipe/' },
        expect.any(Object)
      )
    })
  })

  describe('saved-page submit', () => {
    it('paste mode calls useImportHtml with html and source_url as JSON', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      // Switch to paste mode (default) and fill in the fields
      const sourceUrlInput = screen.getByPlaceholderText(/https:\/\/www\.kitchensanctuary/i)
      await user.type(sourceUrlInput, 'https://www.kitchensanctuary.com/recipe')

      const htmlTextarea = screen.getByPlaceholderText(/paste the full page source/i)
      await user.type(htmlTextarea, '<html><body>content</body></html>')

      await user.click(screen.getByRole('button', { name: /read recipe/i }))

      expect(mockImportHtmlMutate).toHaveBeenCalledWith(
        {
          html: '<html><body>content</body></html>',
          source_url: 'https://www.kitchensanctuary.com/recipe',
        },
        expect.any(Object)
      )
    })

    it('file upload mode submits via importHtml with file and source_url', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      await user.click(screen.getByRole('button', { name: /^upload$/i }))

      const fileInput = screen.getByLabelText(/upload saved page file/i)
      const file = new File(['<html>content</html>'], 'recipe.html', { type: 'text/html' })
      await user.upload(fileInput, file)

      const sourceUrlInput = screen.getByPlaceholderText(/https:\/\/www\.kitchensanctuary/i)
      await user.type(sourceUrlInput, 'https://www.kitchensanctuary.com/recipe')

      await user.click(screen.getByRole('button', { name: /read recipe/i }))

      expect(mockImportHtmlMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          file,
          source_url: 'https://www.kitchensanctuary.com/recipe',
        }),
        expect.any(Object)
      )
    })
  })

  describe('cancel race', () => {
    it('cancelling during fetch prevents in-flight callback from overwriting idle state', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      // Phase is now 'fetching' — capture callbacks before cancelling
      expect(mockImportUrlMutate).toHaveBeenCalledOnce()
      const { onSuccess } = mockImportUrlMutate.mock.calls[0][1]

      // Cancel
      const cancelBtn = await screen.findByRole('button', { name: /cancel/i })
      await user.click(cancelBtn)

      // Link input should be back (idle state)
      expect(screen.getByLabelText(/paste a link/i)).toBeInTheDocument()

      // Fire the stale in-flight callback
      act(() => onSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: [] }))

      // Preview must NOT appear — we are still in idle
      expect(screen.getByLabelText(/paste a link/i)).toBeInTheDocument()
      expect(screen.queryByText('Sweet chili tofu bowls')).not.toBeInTheDocument()
    })
  })

  describe('saved-page error retry', () => {
    it('retry on saved-page error calls importHtml, not importUrl', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const sourceUrlInput = screen.getByPlaceholderText(/https:\/\/www\.kitchensanctuary/i)
      await user.type(sourceUrlInput, 'https://www.kitchensanctuary.com/crispy-sesame')

      const htmlTextarea = screen.getByPlaceholderText(/paste the full page source/i)
      await user.type(htmlTextarea, '<html>content</html>')

      await user.click(screen.getByRole('button', { name: /read recipe/i }))

      expect(mockImportHtmlMutate).toHaveBeenCalledOnce()
      const { onError } = mockImportHtmlMutate.mock.calls[0][1]
      act(() => onError(new Error('Import failed')))

      await waitFor(() => expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument())

      // Reset call history before retry
      mockImportHtmlMutate.mockClear()
      mockImportUrlMutate.mockClear()

      await user.click(screen.getByRole('button', { name: /try again/i }))

      expect(mockImportHtmlMutate).toHaveBeenCalledOnce()
      expect(mockImportUrlMutate).not.toHaveBeenCalled()
    })
  })

  describe('save failure', () => {
    it('shows an error message when bookmark save fails', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/test')
      await user.click(screen.getByRole('button', { name: /fetch recipe/i }))

      const { onSuccess: onImportSuccess } = mockImportUrlMutate.mock.calls[0][1]
      act(() => onImportSuccess({ status: 'success', recipe_id: 'recipe-123', warnings: [] }))

      await waitFor(() => screen.getByRole('button', { name: /save to library/i }))
      await user.click(screen.getByRole('button', { name: /save to library/i }))

      expect(mockBookmarkMutate).toHaveBeenCalledOnce()
      const { onError } = mockBookmarkMutate.mock.calls[0][1]
      act(() => onError(new Error('Network error')))

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument()
      })
    })
  })

  describe('source health alert', () => {
    it('renders no alert when all sources are healthy', () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: [{ source_type: 'hellofresh', status: 'healthy', checked_at: new Date().toISOString(), failing_since: null, detail: null, import_mode: 'link' }],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)

      renderWithProviders(<AddRecipe />)
      expect(screen.queryByText(/have been failing/i)).not.toBeInTheDocument()
    })

    it('renders no alert while health query is loading', () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)

      renderWithProviders(<AddRecipe />)
      expect(screen.queryByText(/have been failing/i)).not.toBeInTheDocument()
    })

    it('renders no alert on health query error', () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      } as ReturnType<typeof useSourceHealth>)

      renderWithProviders(<AddRecipe />)
      expect(screen.queryByText(/have been failing/i)).not.toBeInTheDocument()
    })

    it('shows alert when a source is failing', () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: [{ source_type: 'hellofresh', status: 'failing', checked_at: new Date().toISOString(), failing_since: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), detail: null, import_mode: 'link' }],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)

      renderWithProviders(<AddRecipe />)
      expect(screen.getByText(/HelloFresh imports have been failing/i)).toBeInTheDocument()
      expect(screen.getByText(/the saved page still works in the meantime/i)).toBeInTheDocument()
    })

    it('coordinator sees "See what the check found" link; member does not', () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: [{ source_type: 'hellofresh', status: 'failing', checked_at: new Date().toISOString(), failing_since: new Date().toISOString(), detail: null, import_mode: 'link' }],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)

      // Member: no link
      vi.mocked(useAuth).mockReturnValue({
        currentUser: { id: '1', name: 'Alex', email: 'alex@example.com', role: 'member', dietary_profile: [], allergies: [], disliked_ingredients: [], favorite_ingredients: [], failed_login_attempts: 0, lockout_until: null, lockout_count: 0 },
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
        switchUser: vi.fn(),
      })
      const { unmount } = renderWithProviders(<AddRecipe />)
      expect(screen.queryByRole('link', { name: /see what the check found/i })).not.toBeInTheDocument()
      unmount()

      // Coordinator: link present
      vi.mocked(useAuth).mockReturnValue({
        currentUser: { id: '2', name: 'Sarah', email: 'sarah@example.com', role: 'coordinator', dietary_profile: [], allergies: [], disliked_ingredients: [], favorite_ingredients: [], failed_login_attempts: 0, lockout_until: null, lockout_count: 0 },
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
        switchUser: vi.fn(),
      })
      renderWithProviders(<AddRecipe />)
      const link = screen.getByRole('link', { name: /see what the check found/i })
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', '/profile#recipe-sources')
    })
  })

  describe('failing-source link nudge', () => {
    const failingHFStatus = {
      source_type: 'hellofresh',
      status: 'failing' as const,
      checked_at: new Date().toISOString(),
      failing_since: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      detail: null,
      import_mode: 'link',
    }

    beforeEach(() => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: [failingHFStatus],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)
    })

    it('shows the failing-source nudge when a hellofresh.com link is pasted while HF is failing', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls')

      await waitFor(() => {
        expect(screen.getByText(/HelloFresh has been failing its daily check/i)).toBeInTheDocument()
      })
      expect(mockImportUrlMutate).not.toHaveBeenCalled()
    })

    it('"Try the link anyway" in the nudge posts to /scraper/import-url', async () => {
      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls')

      await waitFor(() =>
        expect(screen.getByRole('button', { name: /try the link anyway/i })).toBeInTheDocument()
      )

      await user.click(screen.getByRole('button', { name: /try the link anyway/i }))

      expect(mockImportUrlMutate).toHaveBeenCalledWith(
        { url: 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls' },
        expect.any(Object),
      )
    })

    it('shows normal "Fetch recipe" button when HF is healthy', async () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: [{ ...failingHFStatus, status: 'healthy', failing_since: null }],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)

      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.hellofresh.com/recipes/sweet-chili-tofu-bowls')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /fetch recipe/i })).toBeInTheDocument()
      })
      expect(screen.queryByText(/has been failing its daily check/i)).not.toBeInTheDocument()
    })

    it('KS URL shows KS nudge even when KS is failing — KS text unchanged', async () => {
      vi.mocked(useSourceHealth).mockReturnValue({
        data: [{ source_type: 'kitchen_sanctuary', status: 'failing', checked_at: new Date().toISOString(), failing_since: new Date().toISOString(), detail: null, import_mode: 'saved_page' }],
        isLoading: false,
        isError: false,
      } as ReturnType<typeof useSourceHealth>)

      const user = userEvent.setup()
      renderWithProviders(<AddRecipe />)

      const input = screen.getByLabelText(/paste a link/i)
      await user.type(input, 'https://www.kitchensanctuary.com/recipe/')

      await waitFor(() =>
        expect(screen.getByText(/this one needs the saved page/i)).toBeInTheDocument()
      )
      // The failing-source nudge text must NOT appear for KS
      expect(screen.queryByText(/has been failing its daily check/i)).not.toBeInTheDocument()
    })
  })
})
