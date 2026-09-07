package nl.mediamonster.app

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

object BiometricLock {
    private const val AUTHENTICATORS = BiometricManager.Authenticators.BIOMETRIC_WEAK

    fun unavailableReason(activity: FragmentActivity): String? =
        when (BiometricManager.from(activity).canAuthenticate(AUTHENTICATORS)) {
            BiometricManager.BIOMETRIC_SUCCESS -> null
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED ->
                "Stel eerst een vingerafdruk of gezichtsherkenning in via Android"
            BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE ->
                "Dit apparaat heeft geen geschikte biometrische beveiliging"
            BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE ->
                "Biometrische beveiliging is momenteel niet beschikbaar"
            else -> "Biometrische beveiliging kan niet worden gebruikt"
        }

    fun authenticate(
        activity: FragmentActivity,
        title: String,
        onSuccess: () -> Unit,
        onError: (String) -> Unit
    ) {
        unavailableReason(activity)?.let { onError(it); return }
        val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    onSuccess()
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    onError(errString.toString())
                }
            })
        prompt.authenticate(BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle("Bevestig dat jij het bent")
            .setAllowedAuthenticators(AUTHENTICATORS)
            .setNegativeButtonText("Annuleren")
            .build())
    }
}
