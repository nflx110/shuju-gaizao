package local.charles;

import java.awt.AWTEvent;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.Graphics;
import java.awt.GraphicsEnvironment;
import java.awt.Insets;
import java.awt.Toolkit;
import java.awt.Window;
import java.awt.event.WindowEvent;
import java.lang.instrument.Instrumentation;

import javax.swing.BorderFactory;
import javax.swing.JComponent;
import javax.swing.JScrollPane;
import javax.swing.JSplitPane;
import javax.swing.JTabbedPane;
import javax.swing.JTable;
import javax.swing.JTree;
import javax.swing.SwingUtilities;
import javax.swing.Timer;
import javax.swing.UIManager;
import javax.swing.border.AbstractBorder;
import javax.swing.border.Border;
import javax.swing.table.JTableHeader;
import javax.swing.table.TableCellRenderer;
import javax.swing.table.TableColumn;

/**
 * 仅本机注入：给 Charles 表格画格子、滚动区描边、加粗分栏。
 * macOS Aqua 会忽略 JTable.setShowGrid，所以在单元格渲染里补线。
 */
public final class GridAgent {
    private static final Color GRID = new Color(0xB7BEC6);
    private static final Color HEADER_LINE = new Color(0x9AA3AD);
    private static final Color PANE = new Color(0xC5CCD4);
    private static final Dimension CELL = new Dimension(1, 1);
    private static final Border SCROLL_BORDER = BorderFactory.createLineBorder(PANE, 1);
    private static final String MARK = "local.charles.grid";

    public static void premain(String args, Instrumentation inst) {
        Thread boot = new Thread(() -> {
            try {
                Thread.sleep(1200);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                return;
            }
            if (GraphicsEnvironment.isHeadless()) {
                return;
            }
            SwingUtilities.invokeLater(GridAgent::install);
        }, "charles-grid-agent");
        boot.setDaemon(true);
        boot.start();
    }

    public static void agentmain(String args, Instrumentation inst) {
        premain(args, inst);
    }

    private static void install() {
        UIManager.put("Table.gridColor", GRID);
        UIManager.put("Table.showGrid", Boolean.TRUE);
        UIManager.put("Table.showHorizontalLines", Boolean.TRUE);
        UIManager.put("Table.showVerticalLines", Boolean.TRUE);
        UIManager.put("Table.intercellSpacing", CELL);
        UIManager.put("SplitPane.dividerSize", 8);
        applyAll();
        Timer timer = new Timer(900, e -> applyAll());
        timer.setRepeats(true);
        timer.start();
    }

    private static void applyAll() {
        for (Window window : Window.getWindows()) {
            if (window.isDisplayable()) {
                walk(window);
            }
        }
    }

    private static void walk(Component component) {
        patch(component);
        if (component instanceof java.awt.Container container) {
            for (Component child : container.getComponents()) {
                walk(child);
            }
        }
    }

    private static void patch(Component component) {
        if (component instanceof JTable table) {
            patchTable(table);
        } else if (component instanceof JSplitPane split) {
            if (split.getDividerSize() < 8) {
                split.setDividerSize(8);
            }
            split.setBorder(BorderFactory.createLineBorder(PANE, 1));
        } else if (component instanceof JScrollPane scroll) {
            if (!Boolean.TRUE.equals(scroll.getClientProperty(MARK))) {
                scroll.setBorder(SCROLL_BORDER);
                scroll.putClientProperty(MARK, Boolean.TRUE);
            }
        } else if (component instanceof JTabbedPane tabs) {
            tabs.setBorder(BorderFactory.createMatteBorder(1, 0, 0, 0, PANE));
        } else if (component instanceof JTree tree) {
            tree.putClientProperty("JTree.lineStyle", "Horizontal");
        }
    }

    private static void patchTable(JTable table) {
        table.setShowGrid(true);
        table.setShowHorizontalLines(true);
        table.setShowVerticalLines(true);
        table.setGridColor(GRID);
        table.setIntercellSpacing(CELL);
        wrapRenderer(table);
        JTableHeader header = table.getTableHeader();
        if (header != null) {
            header.setBorder(BorderFactory.createMatteBorder(0, 0, 1, 0, HEADER_LINE));
        }
    }

    private static void wrapRenderer(JTable table) {
        if (!Boolean.TRUE.equals(table.getClientProperty(MARK))) {
            table.setDefaultRenderer(Object.class, wrap(table.getDefaultRenderer(Object.class)));
            table.setDefaultRenderer(Number.class, wrap(table.getDefaultRenderer(Number.class)));
            table.setDefaultRenderer(Boolean.class, wrap(table.getDefaultRenderer(Boolean.class)));
            table.putClientProperty(MARK, Boolean.TRUE);
        }
        for (int i = 0; i < table.getColumnModel().getColumnCount(); i++) {
            TableColumn column = table.getColumnModel().getColumn(i);
            TableCellRenderer renderer = column.getCellRenderer();
            if (renderer != null && !(renderer instanceof GridRenderer)) {
                column.setCellRenderer(new GridRenderer(renderer));
            }
        }
    }

    private static TableCellRenderer wrap(TableCellRenderer renderer) {
        if (renderer == null || renderer instanceof GridRenderer) {
            return renderer;
        }
        return new GridRenderer(renderer);
    }

    private static final class GridRenderer implements TableCellRenderer {
        private final TableCellRenderer delegate;

        private GridRenderer(TableCellRenderer delegate) {
            this.delegate = delegate;
        }

        @Override
        public Component getTableCellRendererComponent(
                JTable table,
                Object value,
                boolean isSelected,
                boolean hasFocus,
                int row,
                int column) {
            Component component =
                    delegate.getTableCellRendererComponent(
                            table, value, isSelected, hasFocus, row, column);
            if (component instanceof JComponent jc) {
                Border inner = jc.getBorder();
                if (!(inner instanceof CellGridBorder)) {
                    jc.setBorder(new CellGridBorder(inner));
                }
            }
            return component;
        }
    }

    private static final class CellGridBorder extends AbstractBorder {
        private final Border inner;

        private CellGridBorder(Border inner) {
            this.inner = inner;
        }

        @Override
        public Insets getBorderInsets(Component c, Insets insets) {
            Insets i = inner != null ? inner.getBorderInsets(c) : new Insets(0, 0, 0, 0);
            insets.set(i.top, i.left, Math.max(i.bottom, 1), Math.max(i.right, 1));
            return insets;
        }

        @Override
        public void paintBorder(Component c, Graphics g, int x, int y, int w, int h) {
            if (inner != null) {
                inner.paintBorder(c, g, x, y, w, h);
            }
            g.setColor(GRID);
            int x2 = x + w - 1;
            int y2 = y + h - 1;
            g.drawLine(x, y2, x2, y2);
            g.drawLine(x2, y, x2, y2);
        }
    }

    private GridAgent() {}
}
