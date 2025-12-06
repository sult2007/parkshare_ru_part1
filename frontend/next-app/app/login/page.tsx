import { getServerSession } from 'next-auth/next';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import { SignInCard } from '@/components/auth/sign-in-card';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sign in | ParkShare AI',
  description: 'Authenticate with Google to chat with the AI concierge.'
};

export default async function LoginPage() {
  const session = await getServerSession(authOptions);
  if (session) {
    redirect('/');
  }

  return (
    <div className="flex flex-1 items-center justify-center">
      <SignInCard />
    </div>
  );
}
