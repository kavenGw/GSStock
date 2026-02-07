// 文件上传预览
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('fileInput');
    const preview = document.getElementById('uploadPreview');

    if (fileInput && preview) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) {
                preview.classList.remove('active');
                return;
            }

            // 验证文件类型
            const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
            if (!allowedTypes.includes(file.type)) {
                alert('仅支持 JPG/PNG/GIF/WEBP 格式');
                fileInput.value = '';
                preview.classList.remove('active');
                return;
            }

            // 验证文件大小 (10MB)
            if (file.size > 10 * 1024 * 1024) {
                alert('文件大小不能超过 10MB');
                fileInput.value = '';
                preview.classList.remove('active');
                return;
            }

            // 显示预览
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.src = e.target.result;
                preview.classList.add('active');
            };
            reader.readAsDataURL(file);
        });
    }
});

// 图片放大显示
function showImage(src) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    modalImg.src = src;
    modal.classList.add('active');
}

function closeImage() {
    document.getElementById('imageModal').classList.remove('active');
}

// ESC 键关闭模态框
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeImage();
    }
});
