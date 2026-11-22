import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, FolderPlus } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import SectionHeader from '../components/ui/SectionHeader'
import ConnectedRecipeCard from '../components/recipe/ConnectedRecipeCard'
import { CARD_GRID_CLASS } from '../components/recipe/cardGrid'
import { useRecipeList } from '../api/hooks/useRecipes'
import { useCollectionRecipes, useCollections, useCreateCollection } from '../api/hooks/useCollections'
import type { Collection, RecipeListResponse } from '../api/types'

/**
 * My recipes: what the user has kept. Saved recipes, their own versions of
 * recipes (shown once there is one), and their collections.
 */
export default function MyRecipes() {
  // Always read fresh: saving and unsaving happen on other pages.
  const saved = useRecipeList({ bookmarked: true, limit: 100 }, { staleTime: 0 })
  const variations = useRecipeList({ variations: true, limit: 100 }, { staleTime: 0 })
  const { data: collections, isLoading: collectionsLoading } = useCollections()

  return (
    <PageContainer>
      <div className="py-6 space-y-8">
        <PageTitle>My recipes</PageTitle>

        {variations.data && variations.data.length > 0 && (
          <RecipeSection
            title="My variations"
            subtitle="Your own versions, with your changes to ingredients or steps."
            recipes={variations.data}
          />
        )}

        <section aria-label="Collections" className="space-y-3">
          <SectionHeader subtitle="Group recipes your way: weeknight, for guests, to try.">
            Collections
          </SectionHeader>
          {collectionsLoading && <p className="text-sm text-text-secondary">Loading...</p>}
          {collections && collections.length > 0 && (
            <ul className="grid grid-cols-2 sm:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
              {collections.map((collection) => (
                <CollectionCard key={collection.id} collection={collection} />
              ))}
            </ul>
          )}
          <NewCollection />
        </section>

        <section aria-label="Saved" className="space-y-3">
          <SectionHeader subtitle="Recipes you have bookmarked.">Saved</SectionHeader>
          {saved.isLoading && <p className="text-sm text-text-secondary">Loading...</p>}
          {saved.isError && <p className="text-sm text-text-secondary">Could not load your saved recipes.</p>}
          {saved.data && saved.data.length === 0 && (
            <p className="text-sm text-text-secondary">
              Nothing saved yet. Tap the bookmark on any recipe to keep it here.{' '}
              <Link to="/recipes" className="text-olive underline">
                Browse recipes
              </Link>
            </p>
          )}
          {saved.data && saved.data.length > 0 && (
            <div className={CARD_GRID_CLASS}>
              {saved.data.map((recipe) => (
                <ConnectedRecipeCard key={recipe.id} recipe={recipe} variant="grid" />
              ))}
            </div>
          )}
        </section>
      </div>
    </PageContainer>
  )
}

function RecipeSection({
  title,
  subtitle,
  recipes,
}: {
  title: string
  subtitle: string
  recipes: RecipeListResponse[]
}) {
  return (
    <section aria-label={title} className="space-y-3">
      <SectionHeader subtitle={subtitle}>{title}</SectionHeader>
      <div className={CARD_GRID_CLASS}>
        {recipes.map((recipe) => (
          <ConnectedRecipeCard key={recipe.id} recipe={recipe} variant="grid" />
        ))}
      </div>
    </section>
  )
}

function CollectionCard({ collection }: { collection: Collection }) {
  const { data: recipes } = useCollectionRecipes(collection.id)
  const cover = collection.cover_image ?? recipes?.find((r) => r.source_image)?.source_image ?? null

  return (
    <li>
      <Link
        to={`/my-recipes/collections/${collection.id}`}
        className="block bg-white rounded-card border border-warm-border overflow-hidden"
      >
        <div className="w-full aspect-[4/3] bg-warm-gray">
          {cover ? (
            <img src={cover} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="w-full h-full flex items-center justify-center text-text-tertiary text-xs">
              Empty
            </span>
          )}
        </div>
        <div className="p-3 flex items-center justify-between gap-2">
          <span className="min-w-0">
            <span className="block text-[14px] font-medium text-text-primary truncate">{collection.name}</span>
            <span className="block text-[12px] text-text-secondary">
              {recipes ? `${recipes.length} ${recipes.length === 1 ? 'recipe' : 'recipes'}` : ' '}
            </span>
          </span>
          <ChevronRight size={16} className="text-text-tertiary flex-shrink-0" />
        </div>
      </Link>
    </li>
  )
}

function NewCollection() {
  const create = useCreateCollection()
  const [name, setName] = useState('')
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-3 h-9 rounded-button-sm border border-warm-btn-border bg-white text-text-secondary text-[13px] font-medium"
      >
        <FolderPlus size={14} />
        New collection
      </button>
    )
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const trimmed = name.trim()
        if (!trimmed) return
        create.mutate(trimmed, {
          onSuccess: () => {
            setName('')
            setOpen(false)
          },
        })
      }}
      className="flex gap-2"
    >
      <label htmlFor="my-recipes-new-collection" className="sr-only">
        New collection name
      </label>
      <input
        id="my-recipes-new-collection"
        autoFocus
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Collection name"
        maxLength={255}
        className="flex-1 min-w-0 h-10 rounded-input border border-warm-border bg-white px-3 text-[14px]"
      />
      <button
        type="submit"
        disabled={!name.trim() || create.isPending}
        className="px-3 h-10 rounded-button-sm bg-olive text-white text-[13px] font-medium disabled:opacity-50"
      >
        Create
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="px-3 h-10 rounded-button-sm border border-warm-btn-border text-text-secondary text-[13px]"
      >
        Cancel
      </button>
    </form>
  )
}
