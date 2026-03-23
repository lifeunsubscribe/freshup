import { BrowserRouter, Routes, Route } from 'react-router-dom'
import BottomNav from './components/layout/BottomNav'
import Home from './pages/Home'
import Plan from './pages/Plan'
import Recipes from './pages/Recipes'
import RecipeDetail from './pages/RecipeDetail'
import Pantry from './pages/Pantry'
import Grocery from './pages/Grocery'
import IShopped from './pages/IShopped'
import Profile from './pages/Profile'
import NotFound from './pages/NotFound'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-cream">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/recipes" element={<Recipes />} />
          <Route path="/recipes/:id" element={<RecipeDetail />} />
          <Route path="/pantry" element={<Pantry />} />
          <Route path="/grocery" element={<Grocery />} />
          <Route path="/shopped" element={<IShopped />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        <BottomNav />
      </div>
    </BrowserRouter>
  )
}

export default App
