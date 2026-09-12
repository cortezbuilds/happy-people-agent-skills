#!/usr/bin/env perl
use strict;
use warnings;

# Synthetic values only. This isolates the hw-probe 1.6.5 matching behavior
# without reading or printing identifiers from the running machine.
my $fake_serial  = 'FAKE-SERIAL-123';
my $fake_eui     = '0123456789abcdef';
my $fake_machine = '11111111111111111111111111111111';
my $fake_recovery = 'ABCD-EF01';

my $fixture = join "\n",
    "/dev/disk/by-id/nvme-ACME_MODEL_${fake_serial}_1,",
    "/dev/disk/by-id/nvme-eui.${fake_eui},",
    "/boot/efi/${fake_machine}/Recovery-${fake_recovery}",
    '';

sub stock_1_6_5 {
    my ($content) = @_;
    my %serials;
    while ($content =~ /((\/|^)(ata|nvme|scsi)-[^\s]*_)(.+?)(\-part|[\s\n,])/mg) {
        $serials{$4} = 1;
    }
    for my $serial (sort keys %serials) {
        $content =~ s/_\Q$serial\E\b/_HASHED/g;
    }

    my %wwns;
    while ($content =~ /\/wwn-0x(.+?)\W/g) {
        $wwns{$1} = 1;
    }
    for my $wwn (sort keys %wwns) {
        $content =~ s/(wwn-0x)\Q$wwn\E/${1}HASHED/g;
    }

    # hw-probe 1.6.5 writes the boot_efi listing without a sanitizer.
    return $content;
}

sub proposed_fix {
    my ($content) = @_;
    my %serials;
    while ($content =~ /((\/|^)nvme-[^\s]*_)([^_\s]+)(_\d+)(\-part|[\s\n,])/mg) {
        $serials{$3} = 1;
    }
    while ($content =~ /((\/|^)(ata|nvme|scsi)-[^\s]*_)(.+?)(\-part|[\s\n,])/mg) {
        $serials{$4} = 1;
    }
    for my $serial (sort keys %serials) {
        $content =~ s/_\Q$serial\E(?=\b|_)/_HASHED/g;
    }

    $content =~ s/(nvme-eui\.)[a-f\d]+(?:\-part|(?=[\s\n,]))/${1}HASHED/ig;
    $content =~ s#(\/boot\/efi\/)[a-f\d]{32}(?=/|\n|\z)#${1}...#ig;
    $content =~ s/(Recovery-)[a-f\d]+-[a-f\d]+/${1}.../ig;
    return $content;
}

sub result_line {
    my ($label, $content) = @_;
    my @checks = (
        ['serial',     $fake_serial],
        ['eui',        $fake_eui],
        ['machine-id', $fake_machine],
        ['recovery-id',$fake_recovery],
    );
    print "$label:";
    for my $check (@checks) {
        my ($name, $value) = @$check;
        print " $name=", (index($content, $value) >= 0 ? 'LEAK' : 'redacted');
    }
    print "\n";
}

result_line('stock-1.6.5', stock_1_6_5($fixture));
result_line('proposed-fix', proposed_fix($fixture));
