import RecipeCard, { type RecipeCardProps } from './RecipeCard'
import {
  useMyRecipeRelations,
  useToggleBookmark,
  useToggleLike,
} from '../../api/hooks/useRecipeEngagement'

export type ConnectedRecipeCardProps = Omit<
  RecipeCardProps,
  'isLiked' | 'onLikeToggle' | 'isBookmarked' | 'onBookmarkToggle'
>

/**
 * RecipeCard wired to the current user's bookmark and like state.
 *
 * RecipeCard stays presentational so it remains easy to test and reuse; this
 * wrapper supplies the engagement half. Relation state comes from the shared
 * useMyRecipeRelations map rather than a per-card query, so rendering a grid of
 * cards costs one request instead of one per card. React Query dedupes the
 * subscription across every mounted card.
 *
 * Toggles are optimistic, so the button responds on tap rather than after the
 * round trip.
 */
export default function ConnectedRecipeCard(props: ConnectedRecipeCardProps) {
  const { data: relations } = useMyRecipeRelations()
  const toggleBookmark = useToggleBookmark()
  const toggleLike = useToggleLike()

  const relation = relations?.get(props.recipe.id)
  const isBookmarked = relation?.is_bookmarked ?? false
  const isLiked = relation?.is_liked ?? false

  return (
    <RecipeCard
      {...props}
      isBookmarked={isBookmarked}
      isLiked={isLiked}
      onBookmarkToggle={() =>
        toggleBookmark.mutate({ recipeId: props.recipe.id, next: !isBookmarked })
      }
      onLikeToggle={() => toggleLike.mutate({ recipeId: props.recipe.id, next: !isLiked })}
    />
  )
}
