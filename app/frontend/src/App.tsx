import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import ProtectedAdminRoute from './components/ProtectedAdminRoute';
import AnalyticsTracker from './components/AnalyticsTracker';
import Index from './pages/Index';
import Login from './pages/Login';
import ResetPassword from './pages/ResetPassword';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Applications from './pages/Applications';
import Profile from './pages/Profile';
import ChangePassword from './pages/ChangePassword';
import AdminAnalytics from './pages/AdminAnalytics';
import AdminTrainingPartners from './pages/AdminTrainingPartners';
import AdminTrainingCourses from './pages/AdminTrainingCourses';
import Alerts from './pages/Alerts';
import Trainings from './pages/Trainings';
import AuthCallback from './pages/AuthCallback';
import AuthError from './pages/AuthError';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cache between tab switches so navigation feels instant (no refetch/spinner).
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const AppRoutes = () => (
  <Routes>
    <Route path="/" element={<Index />} />
    <Route path="/login" element={<Login />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
    <Route path="/jobs" element={<ProtectedRoute><Jobs /></ProtectedRoute>} />
    <Route path="/applications" element={<ProtectedRoute><Applications /></ProtectedRoute>} />
    <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
    <Route path="/account/password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />
    <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
    <Route path="/trainings" element={<ProtectedRoute><Trainings /></ProtectedRoute>} />
    <Route path="/admin" element={<ProtectedAdminRoute><AdminAnalytics /></ProtectedAdminRoute>} />
    <Route path="/admin/partners" element={<ProtectedAdminRoute><AdminTrainingPartners /></ProtectedAdminRoute>} />
    <Route path="/admin/courses" element={<ProtectedAdminRoute><AdminTrainingCourses /></ProtectedAdminRoute>} />
    <Route path="/auth/callback" element={<AuthCallback />} />
    <Route path="/auth/error" element={<AuthError />} />
  </Routes>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <BrowserRouter>
        <AuthProvider>
          <AnalyticsTracker />
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
export { AppRoutes };