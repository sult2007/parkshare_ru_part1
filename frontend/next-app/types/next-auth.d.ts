import NextAuth, { DefaultSession, DefaultUser } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    user?: DefaultSession['user'] & {
      id?: string;
      emailVerified?: boolean;
    };
  }

  interface User extends DefaultUser {
    emailVerified?: boolean;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id?: string;
    picture?: string;
    emailVerified?: boolean;
  }
}
