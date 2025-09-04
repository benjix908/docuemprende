// Contiene las funciones reutilizables para el manejo de archivos.

/**
 * Muestra el contenedor de archivos subidos y actualiza la lista.
 * @param {string} fileType - El tipo de documento asociado a los archivos (ej. 'factura', 'guia_de_remision').
 */
async function loadUploadedFiles(fileType) {
    const uploadedFilesContainer = document.getElementById('uploaded-files-container');
    const filesList = document.getElementById('files-list');
    
    try {
        const response = await fetch(`/get_files_by_type/${fileType}`);
        if (response.status === 401) { return; }
        const files = await response.json();
        
        if (files.length > 0) {
            uploadedFilesContainer.classList.remove('hidden');
            filesList.innerHTML = '';
            files.forEach(file => {
                const li = document.createElement('li');
                li.className = 'flex items-center justify-between mb-2';
                li.innerHTML = `
                    <a href="/download/${file.filename}" class="text-blue-600 hover:underline flex-1 truncate mr-2">${file.filename}</a>
                    <div class="flex space-x-2">
                        <button onclick="sendDocumentByEmail('${file.filename}')" class="bg-blue-500 text-white text-sm px-3 py-1 rounded hover:bg-blue-700">Enviar</button>
                        <button onclick="deleteFile('${file.filename}')" class="bg-red-500 text-white text-sm px-3 py-1 rounded hover:bg-red-700">Borrar</button>
                    </div>
                `;
                filesList.appendChild(li);
            });
        } else {
            uploadedFilesContainer.classList.add('hidden');
        }
    } catch (error) {
        console.error('Error al cargar la lista de archivos:', error);
    }
}

/**
 * Sube un archivo al servidor.
 * @param {Event} event - El evento de cambio del input de archivo.
 * @param {string} fileType - El tipo de documento (ej. 'factura').
 */
async function uploadFile(event, fileType) {
    const file = event.target.files[0];
    if (!file) { return; }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);

    try {
        const response = await fetch('/upload_file', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        alert(result.message);
        if (result.success) { 
            loadUploadedFiles(fileType); 
        }
    } catch (error) {
        alert('Error al subir el archivo.');
    }
}

/**
 * Envía un archivo por correo electrónico.
 * @param {string} filename - El nombre del archivo a enviar.
 */
async function sendDocumentByEmail(filename) {
    try {
        const response = await fetch('/send_document_by_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename
            })
        });
        const result = await response.json();
        alert(result.message);
    } catch (error) {
        alert('Error al enviar el correo.');
    }
}

/**
 * Borra un archivo del servidor y la base de datos.
 * @param {string} filename - El nombre del archivo a borrar.
 */
async function deleteFile(filename) {
    if (confirm(`¿Estás seguro de que quieres borrar el archivo "${filename}"? Esta acción no se puede deshacer.`)) {
        try {
            const response = await fetch(`/delete_file/${filename}`, {
                method: 'DELETE'
            });
            const result = await response.json();
            alert(result.message);
            if (result.success) {
                // Obtener el tipo de documento para recargar la lista
                const parts = window.location.pathname.split('/');
                const fileType = parts[parts.length - 1];
                loadUploadedFiles(fileType);
            }
        } catch (error) {
            alert('Error al borrar el archivo.');
        }
    }
}