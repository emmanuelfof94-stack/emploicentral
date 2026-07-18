import { lazy, Suspense } from 'react';
import { ThemeProvider } from 'next-themes';
import { Toaster } from '@/components/ui/sonner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import ProtectedAdminRoute from './components/ProtectedAdminRoute';
import AnalyticsTracker from './components/AnalyticsTracker';
import RouteBackground from './components/RouteBackground';
import InstallPrompt from './components/InstallPrompt';
import WhatsappFab from './components/WhatsappFab';
import ProtectedRecruiterRoute from './components/ProtectedRecruiterRoute';

// Découpage par route (code splitting) : chaque page devient un chunk chargé à
// la demande. Le premier écran (accueil / login) ne télécharge plus tout le
// reste — notamment recharts, qui n'est utilisé que par AdminAnalytics.
const Index = lazy(() => import('./pages/Index'));
const Login = lazy(() => import('./pages/Login'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Jobs = lazy(() => import('./pages/Jobs'));
const Applications = lazy(() => import('./pages/Applications'));
const Profile = lazy(() => import('./pages/Profile'));
const ChangePassword = lazy(() => import('./pages/ChangePassword'));
const AdminAnalytics = lazy(() => import('./pages/AdminAnalytics'));
const AdminTrainingPartners = lazy(() => import('./pages/AdminTrainingPartners'));
const AdminTrainingCourses = lazy(() => import('./pages/AdminTrainingCourses'));
const AdminUsers = lazy(() => import('./pages/AdminUsers'));
const AdminModeration = lazy(() => import('./pages/AdminModeration'));
const Recruiter = lazy(() => import('./pages/Recruiter'));
const RecruiterSignup = lazy(() => import('./pages/RecruiterSignup'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Trainings = lazy(() => import('./pages/Trainings'));
const CourseAccess = lazy(() => import('./pages/CourseAccess'));
const AdminCoursePurchases = lazy(() => import('./pages/AdminCoursePurchases'));
const MarketTrends = lazy(() => import('./pages/MarketTrends'));
const AuthCallback = lazy(() => import('./pages/AuthCallback'));
const AuthError = lazy(() => import('./pages/AuthError'));

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

const PageFallback = () => (
  <div className="flex min-h-[60vh] items-center justify-center">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
  </div>
);

const AppRoutes = () => (
  <Suspense fallback={<PageFallback />}>
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
    <Route path="/cours/:slug" element={<ProtectedRoute><CourseAccess /></ProtectedRoute>} />
    <Route path="/market" element={<ProtectedRoute><MarketTrends /></ProtectedRoute>} />
    <Route path="/admin" element={<ProtectedAdminRoute><AdminAnalytics /></ProtectedAdminRoute>} />
    <Route path="/admin/users" element={<ProtectedAdminRoute><AdminUsers /></ProtectedAdminRoute>} />
    <Route path="/admin/moderation" element={<ProtectedAdminRoute><AdminModeration /></ProtectedAdminRoute>} />
    <Route path="/recruiter/signup" element={<RecruiterSignup />} />
    <Route path="/recruiter" element={<ProtectedRecruiterRoute><Recruiter /></ProtectedRecruiterRoute>} />
    <Route path="/admin/partners" element={<ProtectedAdminRoute><AdminTrainingPartners /></ProtectedAdminRoute>} />
    <Route path="/admin/courses" element={<ProtectedAdminRoute><AdminTrainingCourses /></ProtectedAdminRoute>} />
    <Route path="/admin/achats" element={<ProtectedAdminRoute><AdminCoursePurchases /></ProtectedAdminRoute>} />
    <Route path="/auth/callback" element={<AuthCallback />} />
    <Route path="/auth/error" element={<AuthError />} />
  </Routes>
  </Suspense>
);

const App = () => (
  <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <BrowserRouter>
          <AuthProvider>
            <RouteBackground />
            <AnalyticsTracker />
            <AppRoutes />
            <InstallPrompt />
            <WhatsappFab />
          </AuthProvider>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
export { AppRoutes };