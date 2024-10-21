// Function to calculate the expression entered in the input field
function calculateExpression(inputId, errorId = null) {
    const inputField = document.getElementById(inputId);
    const errorField = errorId ? document.getElementById(errorId) : null;

    inputField.addEventListener('change', function () {
        const expression = inputField.value;
        try {
            // Evaluate the mathematical expression entered by the user
            const result = eval(expression); 

            if (!isNaN(result) && result !== Infinity) {
                inputField.value = result.toFixed(2);
                if (errorField) {
                    Swal.fire({
                        icon:'warning',
                        text:'Invalid input or calculation error',  
                    })
                }
            } else {
                throw new Error("Invalid calculation");
            }
        } catch (error) {
            if (errorField) {
                Swal.fire({
                    icon:'warning',
                    text:'Invalid input or calculation error',  
                })
            }
        }
    });
}
