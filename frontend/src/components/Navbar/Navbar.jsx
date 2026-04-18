import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import styles from './Navbar.module.css';

const NAV_ITEMS = [
    { path: '/chat', icon: '💬', labelKey: 'nav.chat' },
    { path: '/papers', icon: '📚', labelKey: 'nav.papers' },
    { path: '/knowledge', icon: '💡', labelKey: 'nav.knowledge' },
    { path: '/writing', icon: '✍️', labelKey: 'nav.writing' },
];

function Navbar() {
    const location = useLocation();
    const navigate = useNavigate();
    const { t, i18n } = useTranslation();

    const toggleLang = () => i18n.changeLanguage(i18n.language === 'zh' ? 'en' : 'zh');

    return (
        <nav className={styles.navbar}>
            <div className={styles.logo}>
                <span className={styles.logoIcon}>📖</span>
                <span className={styles.logoText}>PaperChat</span>
            </div>

            <div className={styles.navItems}>
                {NAV_ITEMS.map(item => (
                    <div
                        key={item.path}
                        className={`${styles.navItem} ${location.pathname === item.path ? styles.active : ''}`}
                        onClick={() => navigate(item.path)}
                        title={t(item.labelKey)}
                    >
                        <span className={styles.navIcon}>{item.icon}</span>
                        <span className={styles.navLabel}>{t(item.labelKey)}</span>
                    </div>
                ))}
            </div>

            <div className={styles.userSection}>
                <div
                    className={`${styles.navItem} ${location.pathname === '/settings' ? styles.active : ''}`}
                    onClick={() => navigate('/settings')}
                    title={t('nav.systemSettings')}
                >
                    <span className={styles.navIcon}>⚙️</span>
                    <span className={styles.navLabel}>{t('nav.settings')}</span>
                </div>
                <div className={styles.userName} title={t('nav.workspace')}>
                    {t('nav.workspace')}
                </div>
                <button
                    className={styles.langToggle}
                    onClick={toggleLang}
                    title={i18n.language === 'zh' ? 'Switch to English' : '切换为中文'}
                >
                    {i18n.language === 'zh' ? 'EN' : '中'}
                </button>
            </div>
        </nav>
    );
}

export default Navbar;
