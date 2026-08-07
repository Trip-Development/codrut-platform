import {
  IdentityMark,
  identityInitials,
  identityMarkVisual,
  type IdentityMarkVisual,
} from "@/components/presentation/identity-mark";

export type ProfileAvatarVisual = IdentityMarkVisual;

export function ProfileAvatar({
  label,
  seed,
  paletteKey,
  className,
  pending = false,
}: {
  label: string;
  seed: string;
  paletteKey?: number | null;
  className?: string;
  pending?: boolean;
}) {
  return (
    <IdentityMark
      kind="person"
      label={label}
      seed={seed}
      paletteKey={paletteKey}
      size="sm"
      className={className}
      pending={pending}
      profile
    />
  );
}

export function profileAvatarVisual(
  seed: string,
  paletteKey?: number | null,
): ProfileAvatarVisual {
  return identityMarkVisual("person", seed, paletteKey);
}

export function profileInitials(label: string): string {
  return identityInitials(label);
}
