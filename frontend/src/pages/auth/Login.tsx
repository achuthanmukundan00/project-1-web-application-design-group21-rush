import React, { useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Grid,
  Alert
} from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { useNavigate, Navigate } from 'react-router-dom';
import { authApi } from '../../services/api';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [alertMsg, setAlertMsg] = useState(''); // Show error messages if login fails
  const [isLoading, setIsLoading] = useState(false);
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/; // Email format checker

  // Redirect to the root if the user is already authenticated
  console.log("login page isAuth:", isAuthenticated)
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!emailRegex.test(email)) {
      setAlertMsg('Please enter a valid email address.');
      return;
    }
    setAlertMsg('');
    setIsLoading(true);

    try {
      const response = await authApi.loginUser({ email, password });

      if ('access_token' in response) {
        login(response.access_token);
        localStorage.setItem('access_token', response.access_token);
        setAlertMsg('Login successful!');
        setTimeout(() => navigate('/'), 1500);
      } else {
        setAlertMsg(response.error || 'Invalid email or password.');
      }
    } catch (error) {
      console.error('Login error:', error);
      setAlertMsg('An error occurred. Please try again later.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" align="center" gutterBottom>
          UofT Secondhand Hub
        </Typography>
        <Typography variant="subtitle1" align="center" gutterBottom>
          Sign in to your account
        </Typography>

        {alertMsg && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {alertMsg}
          </Alert>
        )}

        <form onSubmit={handleLogin}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                label="Email"
                variant="outlined"
                fullWidth
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Password"
                variant="outlined"
                type="password"
                fullWidth
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                fullWidth
                disabled={isLoading}
              >
                {isLoading ? 'Logging in...' : 'Login'}
              </Button>
            </Grid>
          </Grid>
        </form>
        <Typography variant="body2" align="center" sx={{ mt: 2 }}>
          Don’t have an account? <a href="/signup">Sign up</a>
        </Typography>
      </Paper>
    </Container>
  );
};

export default Login;
