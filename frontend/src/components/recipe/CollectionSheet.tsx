import { useState } from 'react'
import { Check, Plus } from 'lucide-react'
import Sheet from '../ui/Sheet'
import {
  useAddToCollection,
  useCollectionRecipes,
  useCollections,
  useCreateCollection,
  useRemoveFromCollection,
} from '../../api/hooks/useCollections'
import type { Collection } from '../../api/types'

interface CollectionSheetProps {
  open: boolean
  onClose: () => void
  recipeId: string
  recipeName: string
}

/**
 * Put a recipe in one or more of the user's collections, or start a new one.
 * Each collection shows whether the recipe is already in it; tapping toggles.
 */
export default function CollectionSheet({ open, onClose, recipeId, recipeName }: CollectionSheetProps) {
  const { data: collections, isLoading, isError } = useCollections()
  const create = useCreateCollection()
  const add = useAddToCollection()
  const [newName, setNewName] = useState('')

  function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    const name = newName.trim()
    if (!name) return
    create.mutate(name, {
      onSuccess: (collection) => {
        setNewName('')
        // A collection started from a recipe starts with that recipe in it.
        add.mutate({ collectionId: collection.id, recipeId })
      },
    })
  }

  return (
    <Sheet open={open} onClose={onClose} title="Add to a collection">
      <div className="px-4 pt-2 pb-4 space-y-4">
        <p className="text-[13px] text-text-secondary">{recipeName}</p>

        {isLoading && <p className="text-sm text-text-secondary">Loading your collections...</p>}
        {isError && <p className="text-sm text-text-secondary">Could not load your collections.</p>}

        {collections && collections.length > 0 && (
          <ul className="divide-y divide-warm-border" aria-label="Your collections">
            {collections.map((collection) => (
              <CollectionRow
                key={collection.id}
                collection={collection}
                recipeId={recipeId}
                open={open}
              />
            ))}
          </ul>
        )}

        <form onSubmit={handleCreate} className="flex gap-2">
          <label htmlFor="new-collection" className="sr-only">
            New collection name
          </label>
          <input
            id="new-collection"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder={collections?.length ? 'New collection' : 'Name your first collection'}
            maxLength={255}
            className="flex-1 min-w-0 h-10 rounded-input border border-warm-border bg-white px-3 text-[14px]"
          />
          <button
            type="submit"
            disabled={!newName.trim() || create.isPending}
            className="flex items-center gap-1 px-3 h-10 rounded-button-sm bg-olive text-white text-[13px] font-medium disabled:opacity-50"
          >
            <Plus size={14} />
            Create
          </button>
        </form>
        {create.isError && (
          <p role="alert" className="text-[13px] text-terra-dark">
            Could not create that collection. Try again.
          </p>
        )}
      </div>
    </Sheet>
  )
}

function CollectionRow({
  collection,
  recipeId,
  open,
}: {
  collection: Collection
  recipeId: string
  open: boolean
}) {
  const { data: recipes } = useCollectionRecipes(collection.id, { enabled: open })
  const add = useAddToCollection()
  const remove = useRemoveFromCollection()
  const contains = recipes?.some((r) => r.id === recipeId) ?? false
  const busy = add.isPending || remove.isPending || recipes === undefined

  function toggle() {
    const vars = { collectionId: collection.id, recipeId }
    if (contains) remove.mutate(vars)
    else add.mutate(vars)
  }

  return (
    <li>
      <button
        onClick={toggle}
        disabled={busy}
        aria-pressed={contains}
        className="flex w-full items-center justify-between gap-3 py-3 min-h-[44px] text-left disabled:opacity-60"
      >
        <span className="min-w-0">
          <span className="block text-[15px] text-text-primary truncate">{collection.name}</span>
          {recipes && (
            <span className="block text-[12px] text-text-secondary">
              {recipes.length} {recipes.length === 1 ? 'recipe' : 'recipes'}
            </span>
          )}
        </span>
        <span
          aria-hidden="true"
          className={`flex items-center justify-center w-7 h-7 rounded-full border ${
            contains ? 'bg-olive border-olive text-white' : 'border-warm-btn-border text-text-secondary'
          }`}
        >
          {contains ? <Check size={14} /> : <Plus size={14} />}
        </span>
      </button>
      {(add.isError || remove.isError) && (
        <p role="alert" className="pb-2 text-[12px] text-terra-dark">
          Could not update this collection. Try again.
        </p>
      )}
    </li>
  )
}
