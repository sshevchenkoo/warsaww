import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service · warsaw,",
  description:
    "The rules for using warsaw, — accounts, acceptable use, third-party content, and disclaimers.",
};

const UPDATED = "13 September 2026";
const CONTACT = "support@transendance.online";

function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="mt-10 text-xl font-black tracking-tight">{children}</h2>;
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="mt-3 leading-relaxed text-fg/80">{children}</p>;
}

export default function TermsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-5 pb-24 pt-10">
      <Link
        href="/"
        className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        ← back
      </Link>

      <h1 className="mt-5 text-balance text-4xl font-black tracking-tighter">
        Terms of Service
      </h1>
      <p className="mt-2 font-mono text-xs tracking-wide text-muted">
        Last updated: {UPDATED}
      </p>

      <P>
        These terms govern your use of <strong>warsaw,</strong> (&ldquo;the service&rdquo;). By
        creating an account or using the service, you agree to them. If you do not agree, please do
        not use the service.
      </P>

      <H2>1. The service</H2>
      <P>
        warsaw, lets you search for events and places in Warsaw, save them, add friends, and share
        listings. It is a free, non-commercial project provided for personal use.
      </P>

      <H2>2. Your account</H2>
      <P>
        You must provide accurate information, keep your credentials confidential, and are
        responsible for activity under your account. Accounts are for individuals — one person per
        account. You may need to verify your email address to use some features.
      </P>

      <H2>3. Acceptable use</H2>
      <P>You agree not to:</P>
      <ul className="mt-3 list-disc space-y-2 pl-6 leading-relaxed text-fg/80">
        <li>break the law or infringe others&rsquo; rights while using the service;</li>
        <li>attempt to access other users&rsquo; data or bypass authentication or rate limits;</li>
        <li>scrape, overload, probe, or disrupt the service or its infrastructure;</li>
        <li>upload unlawful, harmful, or abusive content, including as an avatar or display name;</li>
        <li>misuse the search feature to submit sensitive personal data about others.</li>
      </ul>

      <H2>4. Your content</H2>
      <P>
        You are responsible for the content you add (display name, avatar, shared messages). You
        grant us the limited right to store and display it as needed to operate the features you
        use. You can remove this content or delete your account at any time.
      </P>

      <H2>5. Third-party content and sources</H2>
      <P>
        Event and place listings come from external sources (for example OpenStreetMap, Wikidata,
        and Ticketmaster) and are provided &ldquo;as is.&rdquo; They may be incomplete, inaccurate,
        outdated, or unavailable. Always confirm details (dates, prices, tickets) with the original
        source before relying on them. Links to external sites are outside our control.
      </P>

      <H2>6. Intellectual property</H2>
      <P>
        The service&rsquo;s own code and design belong to their authors. Third-party data and
        trademarks remain the property of their respective owners.
      </P>

      <H2>7. Disclaimers</H2>
      <P>
        The service is provided &ldquo;as is&rdquo; and &ldquo;as available,&rdquo; without
        warranties of any kind, express or implied, including fitness for a particular purpose and
        accuracy of listings. We do not guarantee uninterrupted or error-free operation.
      </P>

      <H2>8. Limitation of liability</H2>
      <P>
        To the extent permitted by law, we are not liable for any indirect or consequential
        damages, or for losses arising from your reliance on event information or from
        interruptions to the service.
      </P>

      <H2>9. Suspension and termination</H2>
      <P>
        We may suspend or terminate accounts that violate these terms or harm the service or its
        users. You may stop using the service and delete your account at any time from your profile
        page.
      </P>

      <H2>10. Changes</H2>
      <P>
        We may update these terms; the &ldquo;last updated&rdquo; date above reflects the latest
        version. Continued use after changes means you accept them.
      </P>

      <H2>11. Governing law</H2>
      <P>
        These terms are governed by the laws of Poland, without regard to conflict-of-laws rules,
        unless a mandatory law of your place of residence provides otherwise.
      </P>

      <H2>12. Contact</H2>
      <P>
        Questions about these terms:{" "}
        <a className="text-accent hover:underline" href={`mailto:${CONTACT}`}>
          {CONTACT}
        </a>
        .
      </P>

      <p className="mt-10 font-mono text-xs text-muted">
        See also our{" "}
        <Link href="/privacy" className="text-accent hover:underline">
          Privacy Policy
        </Link>
        .
      </p>
    </main>
  );
}
