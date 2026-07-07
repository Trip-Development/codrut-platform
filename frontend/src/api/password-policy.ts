export const PASSWORD_MIN_LENGTH = 8;

export const PASSWORD_POLICY_MESSAGE =
  "Parola trebuie să aibă cel puțin 8 caractere și să includă o literă mare, o literă mică, o cifră și un caracter special.";

export function validatePasswordPolicy(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) {
    return PASSWORD_POLICY_MESSAGE;
  }
  if (!/[A-Z]/.test(password)) {
    return PASSWORD_POLICY_MESSAGE;
  }
  if (!/[a-z]/.test(password)) {
    return PASSWORD_POLICY_MESSAGE;
  }
  if (!/[0-9]/.test(password)) {
    return PASSWORD_POLICY_MESSAGE;
  }
  if (!/[^A-Za-z0-9\s]/.test(password)) {
    return PASSWORD_POLICY_MESSAGE;
  }
  return null;
}
