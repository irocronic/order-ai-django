document.addEventListener('DOMContentLoaded', () => {
    const apiUrl = window.APP_CONFIG && window.APP_CONFIG.apiUrl ? window.APP_CONFIG.apiUrl : '';
    const loader = document.getElementById('loader');
    const animatedSections = document.querySelectorAll('.section-anim');
    const appearAnim = () => {
        animatedSections.forEach(sec => {
            const rect = sec.getBoundingClientRect();
            if (rect.top < window.innerHeight * 0.85) sec.classList.add('visible');
            else sec.classList.remove('visible');
        });
    };
    window.addEventListener('scroll', appearAnim);
    appearAnim();

    // Yeni değişkenler: layout ve modal durumu
    let layout = null;
    let isLayoutModalOpen = false;

    let tables = [];

    const fetchData = async () => {
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error(`API Hatası: ${response.status}`);
            const data = await response.json();
            tables = data.tables || [];
            // layout verisini al (istek üzerine eklendi)
            layout = data.layout || (data.business && data.business.layout) || null;
            populatePage(data);
        } catch (error) {
            console.error("Veri alınırken hata oluştu:", error);
            document.body.innerHTML = '<h1 style="color:white; text-align:center; padding: 50px;">Web sitesi yüklenirken bir hata oluştu.</h1>';
        } finally {
            if(loader) {
                loader.style.opacity = '0';
                setTimeout(() => loader.style.display = 'none', 600);
            }
        }
    };

    const populatePage = (data) => {
        const business = data.business;
        const website = data.business.website;
        const menu = data.menu;

        document.title = website.website_title || business.name;
        document.getElementById('nav-logo').textContent = business.name;
        document.getElementById('footer-business-name').textContent = business.name;
        document.getElementById('footer-year').textContent = new Date().getFullYear();

        if (website.about_title && website.about_description) {
            document.getElementById('about-title').textContent = website.about_title;
            document.getElementById('about-description').textContent = website.about_description;
            if (website.about_image) {
                const aboutImg = document.getElementById('about-image');
                aboutImg.src = website.about_image;
                aboutImg.style.display = 'block';
            }
            document.getElementById('nav-link-about').style.display = 'list-item';
        }

        if (website.show_menu && menu && Object.keys(menu).length > 0) {
            const menuContainer = document.getElementById('menu-container');
            let menuHtml = '';
            for (const category in menu) {
                menuHtml += `<div class="category-block"><h3 class="category-title">${category}</h3><div class="menu-grid">`;
                menu[category].forEach(item => {
                    menuHtml += `
                        <div class="menu-item">
                            ${item.image ? `<img src="${item.image}" alt="${item.name}" class="menu-item-image">` : ''}
                            <div class="menu-item-content">
                                <h4 class="menu-item-title">${item.name}</h4>
                                <p class="menu-item-description">${item.description || ''}</p>
                                ${item.price ? `<div class="menu-item-price">${formatCurrency(item.price)}</div>` : ''}
                            </div>
                        </div>
                    `;
                });
                menuHtml += `</div></div>`;
            }
            menuContainer.innerHTML = menuHtml;
            document.getElementById('menu').style.display = 'block';
            document.getElementById('nav-link-menu').style.display = 'list-item';
        }

        if (website.show_contact) {
            let hasContactInfo = false;
            if(website.contact_phone) {
                const el = document.getElementById('contact-phone');
                el.textContent = website.contact_phone;
                el.href = `tel:${website.contact_phone}`;
                document.getElementById('contact-phone-item').style.display = 'block';
                hasContactInfo = true;
            }
            if(website.contact_email) {
                const el = document.getElementById('contact-email');
                el.textContent = website.contact_email;
                el.href = `mailto:${website.contact_email}`;
                document.getElementById('contact-email-item').style.display = 'block';
                hasContactInfo = true;
            }
            if(website.contact_address) {
                document.getElementById('contact-address').textContent = website.contact_address;
                document.getElementById('contact-address-item').style.display = 'block';
                hasContactInfo = true;
            }
            if(website.contact_working_hours) {
                document.getElementById('contact-working-hours').textContent = website.contact_working_hours;
                document.getElementById('contact-hours-item').style.display = 'block';
                hasContactInfo = true;
            }
            if(hasContactInfo) {
                document.getElementById('contact').style.display = 'block';
                document.getElementById('nav-link-contact').style.display = 'list-item';
            }
        }

        // Rezervasyon bölümü: masa seçeneklerini doldur
        if (website.allow_reservations === true) {
            document.getElementById('reservation').style.display = 'block';
            document.getElementById('nav-link-reservation').style.display = 'list-item';

            const tableSelect = document.getElementById('reservation-table');
            tableSelect.innerHTML = '<option value="" disabled selected>Lütfen bir masa seçin...</option>';
            if (tables.length > 0) {
                tables.forEach(table => {
                    const option = document.createElement('option');
                    option.value = table.id;
                    option.textContent = `Masa ${table.table_number}`;
                    tableSelect.appendChild(option);
                });
                tableSelect.disabled = false;
            } else {
                tableSelect.disabled = true;
                const opt = tableSelect.querySelector('option');
                if(opt) opt.textContent = 'Uygun masa bulunamadı.';
            }
        }

        if (website.show_map && website.map_latitude && website.map_longitude) {
            const mapContainer = document.getElementById('map-container-inner');
            const iframe = document.createElement('iframe');
            iframe.loading = 'lazy';
            iframe.allowFullscreen = true;
            iframe.src = `https://maps.google.com/maps?q=${website.map_latitude},${website.map_longitude}&hl=tr&z=${website.map_zoom_level || 15}&output=embed`;
            mapContainer.appendChild(iframe);
            document.getElementById('map').style.display = 'block';
        }

        const socialLinksContainer = document.getElementById('social-links-container');
        let socialHtml = '';
        if(website.facebook_url) socialHtml += `<a href="${website.facebook_url}" target="_blank" title="Facebook"><img src="https://simpleicons.org/icons/facebook.svg" alt="Facebook"></a>`;
        if(website.instagram_url) socialHtml += `<a href="${website.instagram_url}" target="_blank" title="Instagram"><img src="https://simpleicons.org/icons/instagram.svg" alt="Instagram"></a>`;
        if(website.twitter_url) socialHtml += `<a href="${website.twitter_url}" target="_blank" title="Twitter/X"><img src="https://simpleicons.org/icons/x.svg" alt="X"></a>`;
        socialLinksContainer.innerHTML = socialHtml;
        appearAnim();
    };

    const formatCurrency = (value) => {
        return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(value);
    };

    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href && href.startsWith('#')) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    target.classList.add('section-highlight');
                    setTimeout(() => target.classList.remove('section-highlight'), 700);
                }
                // Bootstrap menüyü kapat (mobilde)
                const navbarCollapse = document.getElementById('mainNavbar');
                if (navbarCollapse.classList.contains('show')) {
                    new bootstrap.Collapse(navbarCollapse).hide();
                }
            }
        });
    });

    // Rezervasyon formu: submit işlemi
    const reservationForm = document.getElementById('reservation-form');
    if (reservationForm) {
        reservationForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const form = event.target;
            const alertBox = document.getElementById('reservation-form-alert');
            const reservationFormBlock = document.getElementById('reservation-form-block');
            // Backend'in beklediği alan isimleriyle veri gönder
            const data = {
                table: form.elements['table'].value,
                customer_name: form.elements['name'].value,
                customer_phone: form.elements['phone'].value,
                customer_email: form.elements['email'].value,
                reservation_time: form.elements['date'].value + 'T' + form.elements['time'].value,
                party_size: form.elements['persons'].value,
                notes: form.elements['note'].value,
            };
            try {
                const postUrl = `/api/public/business/${window.APP_CONFIG && window.APP_CONFIG.businessSlug ? window.APP_CONFIG.businessSlug : ''}/reservations/`;
                const response = await fetch(postUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.APP_CONFIG && window.APP_CONFIG.csrfToken ? window.APP_CONFIG.csrfToken : ''
                    },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                if (response.ok) {
                    // Formu gizle, alert mesajını göster
                    form.reset();
                    form.style.display = 'none';
                    // Başlık ve açıklamayı da isteğe bağlı olarak gizleyebilirsiniz
                    const title = reservationFormBlock.querySelector('.reservation-form-title');
                    const desc = reservationFormBlock.querySelector('.reservation-form-desc');
                    if (title) title.style.display = 'none';
                    if (desc) desc.style.display = 'none';
                    alertBox.textContent = 'Rezervasyon talebiniz alındı! Onay için sizinle iletişime geçilecektir.';
                    alertBox.className = 'reservation-form-alert alert alert-success';
                    alertBox.style.display = 'block';
                } else {
                    let errorMessage = 'Bir hata oluştu.';
                    if (typeof result === 'object' && result !== null) {
                        errorMessage = Object.values(result).flat().join(' ');
                    }
                    alertBox.textContent = 'Hata: ' + errorMessage;
                    alertBox.className = 'reservation-form-alert alert alert-danger';
                    alertBox.style.display = 'block';
                }
            } catch (err) {
                alertBox.textContent = 'Rezervasyon gönderilirken bir hata oluştu.';
                alertBox.className = 'reservation-form-alert alert alert-danger';
                alertBox.style.display = 'block';
            }
        });
    }

    // ---------------- Modal ve Vaziyet Planı Fonksiyonları ----------------

    const layoutModalOverlay = document.getElementById('layout-modal-overlay');
    const layoutModalCloseBtn = document.getElementById('layout-modal-close-btn');
    const openLayoutBtn = document.getElementById('open-layout-btn');
    const layoutContainerEl = document.getElementById('layout-container');
    const reservationTableSelect = document.getElementById('reservation-table');

    const openLayoutModal = () => {
        if (!layoutModalOverlay || !layoutContainerEl) return;
        isLayoutModalOpen = true;
        layoutModalOverlay.style.display = 'flex';
        // render layout içine
        renderLayout();
        // body scroll kapat
        document.body.style.overflow = 'hidden';
    };

    const closeLayoutModal = () => {
        if (!layoutModalOverlay) return;
        isLayoutModalOpen = false;
        layoutModalOverlay.style.display = 'none';
        document.body.style.overflow = '';
    };

    // Overlay üzerinde boş alana tıklayınca kapat (x-show @click.self davranışını taklit eder)
    if (layoutModalOverlay) {
        layoutModalOverlay.addEventListener('click', (ev) => {
            if (ev.target === layoutModalOverlay) {
                closeLayoutModal();
            }
        });
    }

    if (layoutModalCloseBtn) {
        layoutModalCloseBtn.addEventListener('click', closeLayoutModal);
    }
    if (openLayoutBtn) {
        openLayoutBtn.addEventListener('click', openLayoutModal);
    }

    // layout verisinin formatına esnek davranacak bir render fonksiyonu
    const renderLayout = () => {
        if (!layoutContainerEl) return;
        // Temizle
        layoutContainerEl.innerHTML = '';

        // layout değişik şekillerde gelebilir:
        // - layout.elements: [ ... ]
        // - layout: [ ... ]
        // - layout.width / layout.height ve layout.elements
        let elements = [];
        let containerWidth = 800;
        let containerHeight = 600;

        if (!layout) {
            // layout yoksa kullanıcıya bilgi göster
            const info = document.createElement('div');
            info.style.padding = '20px';
            info.textContent = 'Vaziyet planı mevcut değil.';
            layoutContainerEl.appendChild(info);
            return;
        }

        if (Array.isArray(layout)) {
            elements = layout;
        } else if (Array.isArray(layout.elements)) {
            elements = layout.elements;
            if (layout.width) containerWidth = layout.width;
            if (layout.height) containerHeight = layout.height;
        } else if (layout.layout && Array.isArray(layout.layout.elements)) {
            elements = layout.layout.elements;
            if (layout.layout.width) containerWidth = layout.layout.width;
            if (layout.layout.height) containerHeight = layout.layout.height;
        } else if (typeof layout === 'object') {
            // olası tek obje yapısı: layout.elements veya doğrudan layout içindeki objeler
            if (layout.elements && Array.isArray(layout.elements)) elements = layout.elements;
            else if (layout.items && Array.isArray(layout.items)) elements = layout.items;
            else {
                // Eğer layout içi doğrudan objelerse key'leri dizi yap
                try {
                    const possible = Object.values(layout).filter(v => typeof v === 'object');
                    if (possible.length > 0) elements = possible;
                } catch (e) {}
            }
            if (layout.width) containerWidth = layout.width;
            if (layout.height) containerHeight = layout.height;
        }

        // container boyutu ayarla (pixel bazlı veya yüzde desteklenebilir)
        layoutContainerEl.style.width = (containerWidth ? containerWidth + 'px' : '800px');
        layoutContainerEl.style.height = (containerHeight ? containerHeight + 'px' : '600px');
        layoutContainerEl.style.position = 'relative';
        layoutContainerEl.style.background = '#f9f9f9';

        // Elementleri render et
        elements.forEach(el => {
            // Beklenen yaygın alanlar: id, type, left, top, width, height, table_number, table_id
            const elDiv = document.createElement('div');
            const isTable = (el.type === 'table') || (el.is_table === true) || (el.table_id !== undefined) || (el.table_number !== undefined);
            elDiv.className = isTable ? 'table-item' : 'layout-element';
            // Pozisyon ve ebatları esnek olarak ayarla: değerler px ya da yüzde olabilir
            const left = (el.left !== undefined) ? el.left : (el.x !== undefined ? el.x : 0);
            const top = (el.top !== undefined) ? el.top : (el.y !== undefined ? el.y : 0);
            const width = (el.width !== undefined) ? el.width : (el.w !== undefined ? el.w : 60);
            const height = (el.height !== undefined) ? el.height : (el.h !== undefined ? el.h : 60);

            // Eğer değer string ise direkt ata, number ise px ekle
            const toCss = (v) => (typeof v === 'number' ? v + 'px' : (typeof v === 'string' ? v : 'auto'));

            elDiv.style.left = toCss(left);
            elDiv.style.top = toCss(top);
            elDiv.style.width = toCss(width);
            elDiv.style.height = toCss(height);
            elDiv.style.display = 'flex';
            elDiv.style.alignItems = 'center';
            elDiv.style.justifyContent = 'center';
            elDiv.style.borderRadius = '6px';
            elDiv.style.boxSizing = 'border-box';
            elDiv.style.overflow = 'hidden';

            // İç metin
            const text = document.createElement('div');
            text.className = 'layout-element-text';
            if (isTable) {
                // Gösterilecek text: Masa numarası veya ID
                const label = el.table_number !== undefined ? `Masa ${el.table_number}` : (el.label || el.name || `Masa ${el.id || el.table_id || ''}`);
                text.textContent = label;
                elDiv.dataset.tableId = (el.table_id !== undefined ? el.table_id : (el.id !== undefined ? el.id : ''));
                elDiv.dataset.tableNumber = (el.table_number !== undefined ? el.table_number : '');
            } else {
                text.textContent = el.label || el.name || (el.type || '');
            }
            elDiv.appendChild(text);

            // Eğer özel şekil istenirse (ör. circle) class veya stil ekleyebiliriz
            if (el.shape === 'circle') {
                elDiv.style.borderRadius = '50%';
            }

            // Click: masa seçimi yapılacaksa rezervasyon select'ini güncelle ve modalı kapat
            elDiv.addEventListener('click', (ev) => {
                ev.stopPropagation();
                if (!isTable) return;
                // seçili sınıflar temizle
                layoutContainerEl.querySelectorAll('.table-item.selected').forEach(n => n.classList.remove('selected'));
                elDiv.classList.add('selected');

                const tableId = elDiv.dataset.tableId || '';
                const tableNumber = elDiv.dataset.tableNumber || '';

                if (tableId) {
                    // Eğer select'te yoksa ekle
                    let opt = Array.from(reservationTableSelect.options).find(o => o.value == tableId);
                    if (!opt) {
                        opt = document.createElement('option');
                        opt.value = tableId;
                        opt.text = tableNumber ? `Masa ${tableNumber}` : `Masa ${tableId}`;
                        reservationTableSelect.appendChild(opt);
                    }
                    reservationTableSelect.value = tableId;
                } else if (tableNumber) {
                    // tableId yoksa, tableNumber ile eşleşen bir option var mı kontrol et
                    let opt = Array.from(reservationTableSelect.options).find(o => o.text.includes(tableNumber));
                    if (!opt) {
                        opt = document.createElement('option');
                        opt.value = tableNumber;
                        opt.text = `Masa ${tableNumber}`;
                        reservationTableSelect.appendChild(opt);
                    }
                    reservationTableSelect.value = opt.value;
                }

                // Modalı kapat
                closeLayoutModal();
            });

            layoutContainerEl.appendChild(elDiv);
        });

        // Eğer eleman yoksa bilgi göster
        if (elements.length === 0) {
            const info = document.createElement('div');
            info.style.padding = '20px';
            info.textContent = 'Vaziyet planında gösterilecek eleman bulunamadı.';
            layoutContainerEl.appendChild(info);
        }
    };

    // ---------------- Son ----------------

    fetchData();
});