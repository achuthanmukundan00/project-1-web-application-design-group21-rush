import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from './styles/theme';
import Home from './pages/Home';
import ProductInfo from './pages/ProductInfo';
import Login from './pages/auth/Login';
import Signup from './pages/auth/Signup';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './context/AuthContext';
import './App.css';
import UserInterests from './pages/auth/UserInterests';


function App() {
  return (
    <AuthProvider> {}
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Router>
          <div className="App">
            <Routes>
              {/* Public Routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route path='/choose-interests-upon-signup' element={<UserInterests/>}/>
              <Route path='/home' element={<Home/>}/>
              {/* Protected Routes */}
              <Route path="/" element={<ProtectedRoute component={Home} />} />
              <Route path="/productInfo" element={<ProtectedRoute component={ProductInfo} />} />

            </Routes>
          </div>
        </Router>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
