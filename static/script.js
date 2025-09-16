document.addEventListener('DOMContentLoaded', () => {
    const roles = document.querySelectorAll('.role');
    const roleInput = document.getElementById('role');
    const selectedText = document.querySelector('.selected-role');  // Updated selector

    if (roles.length > 0 && roleInput) {  // Ensure elements exist
        roles.forEach(role => {
            role.addEventListener('click', () => {
                roles.forEach(r => r.classList.remove('selected'));
                role.classList.add('selected');
                const selectedRole = role.dataset.role;
                roleInput.value = selectedRole;
                if (selectedText) {
                    selectedText.textContent = `Selected: ${selectedRole.charAt(0).toUpperCase() + selectedRole.slice(1)}`;
                }
            });
        });
    }
});