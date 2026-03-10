import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  isAuthenticated: boolean;
  mnemonic: string | null;
  did: string | null;
  walletAddress: string | null;
  publicKey: string | null;
  privateKey: string | null;
  
  login: (mnemonic: string, address: string, pubKey: string, privKey: string, did: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      mnemonic: null,
      did: null,
      walletAddress: null,
      publicKey: null,
      privateKey: null,

      login: (mnemonic, address, pubKey, privKey, did) => {
        set({
          isAuthenticated: true,
          mnemonic,
          did: did,
          walletAddress: address,
          publicKey: pubKey,
          privateKey: privKey
        });
      },

      logout: () => {
        set({
          isAuthenticated: false,
          mnemonic: null,
          did: null,
          walletAddress: null,
          publicKey: null,
          privateKey: null
        });
      }
    }),
    {
      name: 'aether-auth-storage',
    }
  )
);
