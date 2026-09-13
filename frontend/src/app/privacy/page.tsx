import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy · warsaw,",
  description:
    "What data warsaw, collects, why, who it is shared with, and how you can access or delete it.",
};

const UPDATED = "13 September 2026";
const CONTACT = "privacy@transendance.online";

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-10 text-xl font-black tracking-tight">{children}</h2>;
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="mt-3 leading-relaxed text-fg/80">{children}</p>;
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-5 pb-24 pt-10">
      <Link
        href="/"
        className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        ← back
      </Link>

      <h1 className="mt-5 text-balance text-4xl font-black tracking-tighter">
        Privacy Policy
      </h1>
      <p className="mt-2 font-mono text-xs tracking-wide text-muted">
        Last updated: {UPDATED}
      </p>

      <P>
        <strong>warsaw,</strong> (&ldquo;the service&rdquo;, &ldquo;we&rdquo;) helps you discover
        events and places in Warsaw through natural-language search. This policy explains what
        personal data we collect, why we collect it, who processes it on our behalf, and the
        choices you have. It reflects what the application actually does.
      </P>

      <H2>Data we collect</H2>
      <P>
        <strong>Account data.</strong> When you register with email and password, we store your
        email address and a salted <em>bcrypt</em> hash of your password — never the password
        itself. If you sign in with Google, we store your Google account identifier and basic
        profile details (name, email) that Google returns. You may also add a display name and
        upload an avatar image, which we resize and store.
      </P>
      <P>
        <strong>Activity data.</strong> Items you save, friend requests and friendships, events
        you share with friends, and a &ldquo;last seen&rdquo; timestamp used to show whether you
        are currently online.
      </P>
      <P>
        <strong>Search data.</strong> The text of your search prompts and the structured
        &ldquo;intent&rdquo; we derive from them are logged so we can monitor quality and improve
        ranking. Do not include sensitive personal information in search prompts.
      </P>
      <P>
        <strong>Technical data.</strong> A signed session cookie keeps you logged in; it also
        carries an anonymous session identifier used to enforce a daily search limit. We collect
        basic operational logs and metrics (e.g. request timing, errors) to run the service.
      </P>

      <H2>How we use your data</H2>
      <P>
        To authenticate you and keep you signed in; to provide the core features (search, saving,
        friends, sharing, presence); to send you a verification code and account-related emails;
        to prevent abuse and enforce rate limits; and to operate, secure, and improve the service.
      </P>

      <H2>Who we share it with</H2>
      <P>
        We do not sell your data. We rely on the following processors, and only the data needed
        for each is shared:
      </P>
      <ul className="mt-3 list-disc space-y-2 pl-6 leading-relaxed text-fg/80">
        <li>
          <strong>Google</strong> — sign-in (OAuth), if you choose to log in with Google.
        </li>
        <li>
          <strong>Resend</strong> — delivery of verification and account emails (receives your
          email address).
        </li>
        <li>
          <strong>Anthropic</strong> and <strong>Voyage AI</strong> — your search prompt is sent
          to interpret the query and rank results.
        </li>
        <li>
          <strong>DigitalOcean</strong> — hosting and managed database.
        </li>
      </ul>
      <P>
        Event and place listings are gathered from public sources (e.g. OpenStreetMap, Wikidata,
        Ticketmaster). Those sources receive event data, not your account information.
      </P>

      <H2>Retention</H2>
      <P>
        We keep account and activity data while your account exists. Search logs are retained for
        quality and abuse-prevention purposes. When you delete your account, your account data and
        the records tied to it (saved items, friendships, shares, avatar) are deleted.
      </P>

      <H2>Your rights</H2>
      <P>
        You can access and update your profile in the app, export a copy of your data, and delete
        your account. Depending on where you live (e.g. under the EU GDPR) you may also have rights
        to rectification, restriction, and to lodge a complaint with a supervisory authority. To
        exercise any of these, use the controls on your profile page or contact us at{" "}
        <a className="text-accent hover:underline" href={`mailto:${CONTACT}`}>
          {CONTACT}
        </a>
        .
      </P>

      <H2>Security</H2>
      <P>
        Passwords are hashed, all browser traffic uses HTTPS, and access to user-owned records is
        enforced at the database level (row-level security) in addition to application checks. No
        system is perfectly secure, but we take reasonable measures to protect your data.
      </P>

      <H2>Children</H2>
      <P>
        The service is not directed to children under 16, and we do not knowingly collect their
        data.
      </P>

      <H2>Changes</H2>
      <P>
        We may update this policy; material changes will be reflected by the &ldquo;last
        updated&rdquo; date above.
      </P>

      <H2>Contact</H2>
      <P>
        Questions about this policy or your data:{" "}
        <a className="text-accent hover:underline" href={`mailto:${CONTACT}`}>
          {CONTACT}
        </a>
        .
      </P>

      <p className="mt-10 font-mono text-xs text-muted">
        See also our{" "}
        <Link href="/terms" className="text-accent hover:underline">
          Terms of Service
        </Link>
        .
      </p>
    </main>
  );
}
