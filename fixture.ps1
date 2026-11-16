# Owned acceptance fixture only. No focus activation, no files/user data, closes after 180s.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing -TypeDefinition @'
using System;
using System.Windows.Forms;
public class ComputerControlFixture : Form {
    protected override bool ShowWithoutActivation { get { return true; } }
    protected override CreateParams CreateParams { get { var p=base.CreateParams; p.ExStyle |= 0x08000000; return p; } }
    public ComputerControlFixture() {
        Text = "Computer Control Acceptance Fixture";
        Width=430; Height=220; Left=80; Top=80;
        StartPosition=FormStartPosition.Manual;
        var input = new TextBox { Name="input", AccessibleName="Control input", Left=20, Top=20, Width=360, Text="initial" };
        var output = new Label { Name="output", Left=20, Top=105, Width=360, Text="pending" };
        var button = new Button { Name="apply", AccessibleName="Apply fixture", Left=20, Top=60, Width=140, Text="Apply fixture" };
        button.Click += (s,e) => { output.Text = "applied: " + input.Text; };
        Controls.Add(input); Controls.Add(button); Controls.Add(output);
        var timer = new Timer { Interval=180000 };
        timer.Tick += (s,e) => { timer.Stop(); Close(); };
        timer.Start();
    }
}
'@
[System.Windows.Forms.Application]::Run([ComputerControlFixture]::new())
