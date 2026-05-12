document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('searchInput');
    const negozioSelect = document.getElementById('negozioSelect');
    const sortPriceToggle = document.getElementById('sortPrice');

    const resultsGrid = document.getElementById('resultsGrid');
    const loader = document.getElementById('loader');
    const emptyState = document.getElementById('emptyState');
    const aiSection = document.getElementById('aiSection');

    // URL di produzione su Railway
    const API_BASE_URL = 'https://tecnomatsearch-production.up.railway.app';

    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query = searchInput.value.trim();
        if (!query) return;

        const negozio = negozioSelect.value;
        const sortPrice = sortPriceToggle.checked;

        // UI Updates
        emptyState.classList.add('hidden');
        aiSection.classList.add('hidden');
        aiSection.innerHTML = '';
        resultsGrid.innerHTML = '';
        loader.classList.remove('hidden');

        try {
            // Costruisci l'URL con i parametri
            const url = new URL(`${API_BASE_URL}/api/search`);
            url.searchParams.append('q', query);
            url.searchParams.append('negozio', negozio);
            url.searchParams.append('n', 10);
            if (sortPrice) url.searchParams.append('sort_price', 'true');

            // Chiamata all'API
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error('Errore di rete o server offline');
            }

            const data = await response.json();

            loader.classList.add('hidden');

            // Mostra consigli AI se presenti
            if (data.ai_insights) {
                renderAIInsights(data.ai_insights);
            }

            if (data.results && data.results.length > 0) {
                renderResults(data.results);
            } else {
                showEmptyState("Nessun prodotto trovato. Prova con termini diversi.");
            }

        } catch (error) {
            console.error("Errore durante la ricerca:", error);
            loader.classList.add('hidden');
            showEmptyState("Impossibile connettersi al server. Assicurati che l'API sia attiva.");
        }
    });

    function renderResults(results) {
        resultsGrid.innerHTML = '';

        results.forEach(prod => {
            const isTecnomat = prod.source === 'TECNOMAT';
            const badgeClass = isTecnomat ? 'tecnomat' : 'leroy';

            const card = document.createElement('a');
            card.href = prod.url;
            card.target = '_blank';
            card.className = 'product-card';

            card.innerHTML = `
                <div class="badge ${badgeClass}">${prod.source}</div>
                <h3 class="product-name">${prod.name}</h3>
                <div class="product-price">${prod.price}</div>
                
                <div class="product-meta">
                    <div class="meta-item">
                        <i data-lucide="package" class="meta-icon"></i>
                        <span>${prod.stock}</span>
                    </div>
                    ${isTecnomat ? `
                    <div class="meta-item">
                        <i data-lucide="map-pin" class="meta-icon"></i>
                        <span>${prod.location}</span>
                    </div>
                    ` : ''}
                </div>
            `;

            resultsGrid.appendChild(card);
        });

        // Inizializza le nuove icone lucide appena inserite
        lucide.createIcons();
    }

    function renderAIInsights(insights) {
        aiSection.innerHTML = `
            <div class="ai-header">
                <i data-lucide="sparkles"></i>
                Consigli di Nikituttofare
            </div>
            <div class="ai-advice">${insights.advice}</div>
            <div class="ai-kit-container" id="kitContainer"></div>
        `;

        const kitContainer = document.getElementById('kitContainer');
        insights.kit.forEach(item => {
            const tag = document.createElement('div');
            tag.className = 'kit-tag';
            tag.innerHTML = `<i data-lucide="plus-circle"></i> ${item}`;
            tag.onclick = () => {
                searchInput.value = item;
                searchForm.dispatchEvent(new Event('submit'));
            };
            kitContainer.appendChild(tag);
        });

        aiSection.classList.remove('hidden');
        lucide.createIcons();
    }

    function showEmptyState(message) {
        emptyState.innerHTML = `
            <i data-lucide="alert-circle" class="icon-empty"></i>
            <p>${message}</p>
        `;
        emptyState.classList.remove('hidden');
        lucide.createIcons();
    }
});
