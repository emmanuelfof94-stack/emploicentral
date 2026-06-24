import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { client } from '../lib/api';

interface User {
  id: string;
  email: string;
  name?: string;
  role?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // Fast path: no token → unauthenticated, no network round-trip, no spinner.
    if (!localStorage.getItem('token')) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const res = await client.auth.me();
      setUser(res?.data ? (res.data as User) : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const refreshAuth = useCallback(async () => {
    await checkAuth();
  }, [checkAuth]);

  // Local auth stores the JWT in localStorage and reloads to /dashboard,
  // so login() just routes to the login screen.
  const login = () => {
    window.location.assign('/login');
  };

  const logout = () => {
    client.auth.logout();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshAuth }}>
      {children}
    </AuthContext.Provider>
  );
};
