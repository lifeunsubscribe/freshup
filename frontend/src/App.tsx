import { BrowserRouter, Routes, Route, useLocation, useParams, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/auth/ProtectedRoute'
import BottomNav from './components/layout/BottomNav'
import Login from './pages/Login'
import Home from './pages/Home'
import Plan from './pages/Plan'
import PlanWeek from './pages/PlanWeek'
import ProfileMenu from './components/layout/ProfileMenu'
import MyRecipes from './pages/MyRecipes'
import MyCollection from './pages/MyCollection'
import Recipes from './pages/Recipes'
import AddRecipe from './pages/AddRecipe'
import RecipeDetail from './pages/RecipeDetail'
import Pantry from './pages/Pantry'
import Grocery from './pages/Grocery'
import IShopped from './pages/IShopped'
import Profile from './pages/Profile'
import Welcome from './pages/Welcome'
import Collection, { LegacyCollectionRedirect } from './pages/Collection'
import NotFound from './pages/NotFound'
import { ErrorBoundary } from './components/errors'
import AuthErrorFallback from './components/errors/AuthErrorFallback'

// Forces a full remount when source or slug changes, resetting all walk state.
function CollectionRoute() {
  const { source, slug } = useParams<{ source: string; slug: string }>()
  return <Collection key={`${source}/${slug}`} />
}

function AppContent() {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentUser, isAuthenticated, isLoading } = useAuth()
  const isLoginPage = location.pathname === '/login'
  const isWelcomePage = location.pathname === '/welcome'

  // Redirect un-onboarded users to the first-run quiz
  useEffect(() => {
    if (
      !isLoading &&
      isAuthenticated &&
      currentUser?.onboarded_at === null &&
      !isWelcomePage &&
      !isLoginPage
    ) {
      navigate('/welcome', { replace: true })
    }
  }, [isLoading, isAuthenticated, currentUser?.onboarded_at, isWelcomePage, isLoginPage, navigate])

  return (
    <div className="relative min-h-screen bg-cream">
      {!isLoginPage && !isWelcomePage && isAuthenticated && <ProfileMenu />}
      <Routes>
        {/* Public route */}
        <Route path="/login" element={<Login />} />

        {/* Protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plan"
          element={
            <ProtectedRoute>
              <Plan />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-recipes"
          element={
            <ProtectedRoute>
              <MyRecipes />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-recipes/collections/:id"
          element={
            <ProtectedRoute>
              <MyCollection />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plan/:weekStart"
          element={
            <ProtectedRoute>
              <PlanWeek />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recipes"
          element={
            <ProtectedRoute>
              <Recipes />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recipes/add"
          element={
            <ProtectedRoute>
              <AddRecipe />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recipes/:id"
          element={
            <ProtectedRoute>
              <RecipeDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pantry"
          element={
            <ProtectedRoute>
              <Pantry />
            </ProtectedRoute>
          }
        />
        <Route
          path="/grocery"
          element={
            <ProtectedRoute>
              <Grocery />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shopped"
          element={
            <ProtectedRoute>
              <IShopped />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/welcome"
          element={
            <ProtectedRoute>
              <Welcome />
            </ProtectedRoute>
          }
        />
        <Route
          path="/browse/:source/:slug"
          element={
            <ProtectedRoute>
              <CollectionRoute />
            </ProtectedRoute>
          }
        />
        <Route
          path="/browse/hellofresh/:slug"
          element={
            <ProtectedRoute>
              <LegacyCollectionRedirect />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
      {!isLoginPage && !isWelcomePage && <BottomNav />}
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary fallback={(error, resetError) => <AuthErrorFallback error={error} resetError={resetError} />}>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

export default App
