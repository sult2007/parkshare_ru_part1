import { NextAuthOptions } from 'next-auth';
import GoogleProvider from 'next-auth/providers/google';

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? '',
      profile(profile) {
        return {
          id: profile.sub,
          name: profile.name,
          email: profile.email,
          image: profile.picture,
          emailVerified: profile.email_verified
        };
      }
    })
  ],
  session: {
    strategy: 'jwt'
  },
  callbacks: {
    async signIn({ profile }) {
      if (profile && 'email_verified' in profile) {
        return Boolean(profile.email_verified);
      }
      return false;
    },
    async jwt({ token, profile }) {
      if (profile) {
        token.id = (profile as { sub?: string }).sub;
        token.picture = (profile as { picture?: string }).picture;
        token.emailVerified = Boolean((profile as { email_verified?: boolean }).email_verified);
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = typeof token.id === 'string' ? token.id : undefined;
        session.user.image = typeof token.picture === 'string' ? token.picture : session.user.image;
        session.user.emailVerified = Boolean(token.emailVerified);
      }
      return session;
    }
  },
  pages: {
    signIn: '/login'
  },
  secret: process.env.NEXTAUTH_SECRET
};
