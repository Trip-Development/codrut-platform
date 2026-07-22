export const PASSWORD_MIN_LENGTH = 12;
export const PASSWORD_MAX_LENGTH = 128;

export const PASSWORD_POLICY_MESSAGE = "Parola trebuie să aibă cel puțin 12 caractere.";
export const PASSWORD_POLICY_HELP = `Minim ${PASSWORD_MIN_LENGTH} și maximum ${PASSWORD_MAX_LENGTH} de caractere. Parolele comune sau compromise sunt respinse.`;

const commonPasswords = new Set([
  "123456789012",
  "administrator",
  "changeme1234",
  "codrut123456",
  "letmeinplease",
  "parola123456",
  "password" + "1234",
  "qwerty123456",
  "qwertyuiop12",
  "welcome12345",
]);

export function validatePasswordPolicy(password: string): string | null {
  const characterCount = Array.from(password).length;

  if (characterCount < PASSWORD_MIN_LENGTH) {
    return PASSWORD_POLICY_MESSAGE;
  }
  if (characterCount > PASSWORD_MAX_LENGTH) {
    return `Parola nu poate depăși ${PASSWORD_MAX_LENGTH} de caractere.`;
  }
  if (commonPasswords.has(password.trim().toLocaleLowerCase("ro-RO"))) {
    return "Parola este prea frecventă. Alege o frază mai greu de ghicit.";
  }
  return null;
}
