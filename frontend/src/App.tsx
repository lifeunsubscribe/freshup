import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/auth/ProtectedRoute'
import BottomNav from './components/layout/BottomNav'
import Login from './pages/Login'
import Home from './pages/Home'
import Plan from './pages/Plan'
import Recipes from './pages/Recipes'
import RecipeDetail from './pages/RecipeDetail'
import Pantry from './pages/Pantry'
import Grocery from './pages/Grocery'
import IShopped from './pages/IShopped'
import Profile from './pages/Profile'
import NotFound from './pages/NotFound'

function AppContent() {
  const location = useLocation()
  const isLoginPage = location.pathname === '/login'

  return (
    <div className="min-h-screen bg-cream">
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
              path="/recipes"
              element={
                <ProtectedRoute>
                  <Recipes />
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
        <Route path="*" element={<NotFound />} />
      </Routes>
      {!isLoginPage && <BottomNav />}
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
