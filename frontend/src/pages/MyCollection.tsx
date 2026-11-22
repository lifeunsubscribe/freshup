import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import ConnectedRecipeCard from '../components/recipe/ConnectedRecipeCard'
import { CARD_GRID_CLASS } from '../components/recipe/cardGrid'
import {
  useCollectionRecipes,
  useCollections,
  useDeleteCollection,
  useRemoveFromCollection,
} from '../api/hooks/useCollections'

/** One of the user's collections: its recipes, with a way to take each out. */
export default function MyCollection() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: collections } = useCollections()
  const { data: recipes, isLoading, isError } = useCollectionRecipes(id)
  const remove = useRemoveFromCollection()
  const deleteCollection = useDeleteCollection()
  const collection = collections?.find((c) => c.id === id)

  return (
    <PageContainer>
      <div className="py-6 space-y-4">
        <Link to="/my-recipes" className="inline-flex items-center gap-1 text-[13px] text-olive">
          <ChevronLeft size={14} />
          My recipes
        </Link>
        <PageTitle>{collection?.name ?? 'Collection'}</PageTitle>

        {isLoading && <p className="text-sm text-text-secondary">Loading...</p>}
        {isError && <p className="text-sm text-text-secondary">Could not load this collection.</p>}
        {recipes && recipes.length === 0 && (
          <p className="text-sm text-text-secondary">
            Nothing here yet. Use "Add to a collection" on any recipe.
          </p>
        )}
        {recipes && recipes.length > 0 && (
          <ul className={CARD_GRID_CLASS} aria-label="Recipes in this collection">
            {recipes.map((recipe) => (
              <li key={recipe.id} className="flex flex-col gap-1.5">
                <ConnectedRecipeCard recipe={recipe} variant="grid" />
                <button
                  onClick={() => remove.mutate({ collectionId: id, recipeId: recipe.id })}
                  disabled={remove.isPending}
                  aria-label={`Take ${recipe.name} out of this collection`}
                  className="self-start text-[12px] text-text-secondary underline disabled:opacity-50"
                >
                  Take out
                </button>
              </li>
            ))}
          </ul>
        )}

        {collection && (
          <button
            onClick={() => {
              if (window.confirm(`Delete the collection "${collection.name}"? The recipes stay saved.`)) {
                deleteCollection.mutate(id, { onSuccess: () => navigate('/my-recipes') })
              }
            }}
            className="pt-4 text-[13px] text-terra-dark underline"
          >
            Delete this collection
          </button>
        )}
      </div>
    </PageContainer>
  )
}
